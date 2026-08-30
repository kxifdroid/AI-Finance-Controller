"""
Comprehensive Test Suite for Phase 2: Reconciliation Engine Upgrades.

Tests:
1. EvidenceBuilder: JSON schema structure, values, formatting, serialization.
2. FeeCalculator: Net settlement, 18% GST calculation, variance validation.
3. ExactMatcher: Layer 1 exact matching on reference, date, and amount.
4. SettlementMatcher: Many-to-one batch settlement subset-sum resolution.
5. DuplicateDetector: Source-level collision scanning via hash and fingerprint.
6. Chained 3-Way Engine: Leg 1 + Leg 2 + Batch Settlement + Expanded Exceptions + Audit Logs.
"""

import json
import asyncio
import pytest
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.models.reconciliation import Match, ReconciliationRun
from app.models.exception import ExceptionRecord
from app.models.audit import AuditLog
from app.services.reconciliation.evidence import EvidenceBuilder
from app.services.reconciliation.fee_calculator import FeeCalculator
from app.services.reconciliation.exact_matcher import ExactMatcher, can_auto_clear
from app.services.reconciliation.settlement_matcher import SettlementMatcher
from app.services.reconciliation.duplicate_detector import DuplicateDetector
from app.services.reconciliation.engine import ReconciliationEngine
from app.services.exceptions import ExceptionService
from app.config import settings


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_phase2.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# 1. EvidenceBuilder Tests
# =============================================================================

def test_evidence_builder_match_evidence():
    evidence_str = EvidenceBuilder.build_match_evidence(
        match_type="EXACT",
        rule="exact_amount_date_ref",
        confidence=1.0,
        side_a_fields={"invoice_id": "INV-100", "amount": 2500.0},
        side_b_fields={"gateway_txn_id": "GTW-100", "amount": 2500.0},
        amounts={"expected": 2500.0, "actual": 2500.0, "variance": 0.0},
        dates={"side_a": "2026-08-20", "side_b": "2026-08-20", "delta_days": 0},
        compared_fields={"reference": {"a": "5001", "b": "5001", "match": True}},
        policy_citation="Internal Control Policy 4.1",
        extra_data={"tenant_id": "org_123"},
    )
    assert isinstance(evidence_str, str)
    parsed = json.loads(evidence_str)
    assert parsed["evidence_type"] == "MATCH"
    assert parsed["match_type"] == "EXACT"
    assert parsed["confidence"] == 1.0
    assert parsed["amounts"]["variance"] == 0.0
    assert parsed["dates"]["delta_days"] == 0
    assert parsed["policy_citation"] == "Internal Control Policy 4.1"
    assert parsed["extra"]["tenant_id"] == "org_123"


def test_evidence_builder_exception_evidence():
    evidence_str = EvidenceBuilder.build_exception_evidence(
        exception_type="FEE_VARIANCE",
        reason="Gateway fee variance of 2.36%",
        amounts={"gross_amount": 10000.0, "net_amount": 9764.0, "discrepancy": 236.0},
        dates={"date": "2026-08-20"},
        references={"ref": "ORD-1234"},
        policy_citation="Razorpay MDR Policy (2.0% MDR + 18% GST on Fee)",
    )
    parsed = json.loads(evidence_str)
    assert parsed["evidence_type"] == "EXCEPTION"
    assert parsed["exception_type"] == "FEE_VARIANCE"
    assert parsed["amounts"]["discrepancy"] == 236.0
    assert "Razorpay MDR" in parsed["policy_citation"]


# =============================================================================
# 2. FeeCalculator Tests
# =============================================================================

def test_fee_calculator_settlement_and_gst():
    gross = 10000.0
    fee = 200.0  # 2% MDR
    tax = FeeCalculator.calculate_gst_on_fee(fee)  # 18% of 200 = 36.0
    assert tax == 36.0

    expected_net = FeeCalculator.calculate_fee_settlement(gross, fee, tax)
    assert expected_net == 9764.0


def test_fee_calculator_validate_variance():
    gross = 10000.0
    # Exact reconciliation with fee and tax
    is_valid, fee_pct, variance, classification = FeeCalculator.validate_fee_variance(
        gross_amount=gross,
        actual_bank_credit=9764.0,
        fee_amount=200.0,
        tax_amount=36.0,
    )
    assert is_valid is True
    assert classification == "FEE_RECONCILED"
    assert variance == 0.0
    assert fee_pct == 0.0236

    # Valid fee variance within 1%-5% without explicit breakdown
    is_valid, fee_pct, variance, classification = FeeCalculator.validate_fee_variance(
        gross_amount=gross,
        actual_bank_credit=9800.0,  # 2% implied fee
    )
    assert is_valid is True
    assert classification == "FEE_VARIANCE"
    assert fee_pct == 0.02

    # Invalid fee mismatch (excessive fee > 5%)
    is_valid, fee_pct, variance, classification = FeeCalculator.validate_fee_variance(
        gross_amount=gross,
        actual_bank_credit=9000.0,  # 10% deduction
    )
    assert is_valid is False
    assert classification == "FEE_MISMATCH"
    assert fee_pct == 0.10


# =============================================================================
# 3. ExactMatcher Tests
# =============================================================================

def test_exact_matcher_leg1_and_leg2():
    # Leg 1: Invoices and Gateways
    inv1 = Invoice(
        invoice_id="INV-001",
        amount=1500.0,
        invoice_date=date(2026, 8, 20),
        invoice_reference="REF-001",
        normalized_amount=1500.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="ref001",
    )
    inv2 = Invoice(
        invoice_id="INV-002",
        amount=8000.0,  # Exceeds materiality ceiling of 5000.0
        invoice_date=date(2026, 8, 20),
        invoice_reference="REF-002",
        normalized_amount=8000.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="ref002",
    )

    gw1 = GatewayTransaction(
        gateway_txn_id="GW-001",
        amount=1500.0,
        transaction_date=date(2026, 8, 20),
        payment_reference="REF-001",
        normalized_amount=1500.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="ref001",
    )
    gw2 = GatewayTransaction(
        gateway_txn_id="GW-002",
        amount=8000.0,
        transaction_date=date(2026, 8, 20),
        payment_reference="REF-002",
        normalized_amount=8000.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="ref002",
    )

    matched, rem_a, rem_b, matched_a_ids, matched_b_ids = ExactMatcher.match(
        side_a_records=[inv1, inv2],
        side_b_records=[gw1, gw2],
        leg_name="Leg 1: Invoice ↔ Gateway",
        allow_fee_variance=False,
    )

    assert len(matched) == 2
    assert "INV-001" in matched_a_ids and "INV-002" in matched_a_ids
    assert len(rem_a) == 0 and len(rem_b) == 0

    # Check materiality decision
    p1 = next(p for p in matched if p["side_a"].invoice_id == "INV-001")
    assert p1["decision"] == "MATCH"
    assert p1["match_type"] == "EXACT"

    p2 = next(p for p in matched if p["side_a"].invoice_id == "INV-002")
    assert p2["decision"] == "MATCH"
    assert p2["match_type"] == "EXACT"


# =============================================================================
# 4. SettlementMatcher (Many-to-One Batch Matching) Tests
# =============================================================================

def test_settlement_matcher_batch_aggregation():
    # 3 Gateway transactions totaling 4500.0 net settlement
    gw1 = GatewayTransaction(
        gateway_txn_id="GW-B1",
        transaction_date=date(2026, 8, 20),
        amount=1000.0,
        gateway_fee=20.0,
        tax_on_fee=3.60,
        net_settlement=976.40,
        payment_reference="BATCH-1",
        normalized_amount=1000.0,
        normalized_date=date(2026, 8, 20),
    )
    gw2 = GatewayTransaction(
        gateway_txn_id="GW-B2",
        transaction_date=date(2026, 8, 21),
        amount=2000.0,
        gateway_fee=40.0,
        tax_on_fee=7.20,
        net_settlement=1952.80,
        payment_reference="BATCH-2",
        normalized_amount=2000.0,
        normalized_date=date(2026, 8, 21),
    )
    gw3 = GatewayTransaction(
        gateway_txn_id="GW-B3",
        transaction_date=date(2026, 8, 21),
        amount=1600.0,
        gateway_fee=32.0,
        tax_on_fee=5.76,
        net_settlement=1562.24,
        payment_reference="BATCH-3",
        normalized_amount=1600.0,
        normalized_date=date(2026, 8, 21),
    )
    total_net = round(976.40 + 1952.80 + 1562.24, 2)  # 4491.44

    # 1 Bank deposit matching sum on 2026-08-22 (within 3 day window)
    bank_batch = BankTransaction(
        bank_txn_id="BNK-BATCH-1",
        transaction_date=date(2026, 8, 22),
        amount=total_net,
        reference="PAYOUT-AGGREGATE",
        normalized_amount=total_net,
        normalized_date=date(2026, 8, 22),
        description="Gateway Daily Batch Payout",
    )

    batch_matches, matched_bank_ids, matched_gw_ids = SettlementMatcher.match_settlements(
        unmatched_banks=[bank_batch],
        unmatched_gateways=[gw1, gw2, gw3],
    )

    assert len(batch_matches) == 1
    assert "BNK-BATCH-1" in matched_bank_ids
    assert len(matched_gw_ids) == 3
    assert "GW-B1" in matched_gw_ids and "GW-B2" in matched_gw_ids and "GW-B3" in matched_gw_ids

    bm = batch_matches[0]
    assert bm["match_type"] == "MANY_TO_ONE"
    assert bm["decision"] in ("MATCH", "REVIEW")
    assert bm["total_net"] == total_net
    assert bm["variance"] == 0.0
    assert bm["evidence_json"] is not None


# =============================================================================
# 5. DuplicateDetector Tests
# =============================================================================

def test_duplicate_detector():
    inv1 = Invoice(
        invoice_id="INV-DUP-1",
        amount=1200.0,
        invoice_date=date(2026, 8, 20),
        invoice_reference="DUP-REF-1",
        raw_row_hash="abc123hash",
    )
    inv2 = Invoice(
        invoice_id="INV-DUP-2",
        amount=1200.0,
        invoice_date=date(2026, 8, 20),
        invoice_reference="DUP-REF-1",
        raw_row_hash="abc123hash",
    )
    inv_unique = Invoice(
        invoice_id="INV-UNIQUE",
        amount=3000.0,
        invoice_date=date(2026, 8, 20),
        invoice_reference="UNIQUE-REF",
        raw_row_hash="uniquehash",
    )

    dup_groups = DuplicateDetector.detect_duplicates([inv1, inv2, inv_unique], "INVOICE")
    assert len(dup_groups) == 1
    assert dup_groups[0]["count"] == 2
    assert dup_groups[0]["primary_record"].invoice_id == "INV-DUP-1"
    assert dup_groups[0]["duplicate_records"][0].invoice_id == "INV-DUP-2"
    assert dup_groups[0]["evidence_json"] is not None


# =============================================================================
# 6. End-to-End Chained Engine Tests with Expanded Exception Taxonomy
# =============================================================================

def test_reconciliation_engine_e2e_with_exceptions_and_duplicates(test_db):
    engine = ReconciliationEngine()

    # 1. Matched Pair: Invoice 1 -> Gateway 1 -> Bank 1
    test_db.add(Invoice(
        invoice_id="INV-M1",
        amount=2000.0,
        invoice_date=date(2026, 8, 20),
        invoice_reference="REF-M1",
        normalized_amount=2000.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="refm1",
        customer_name="Acme Corp",
        normalized_customer="acme corp",
    ))
    test_db.add(GatewayTransaction(
        gateway_txn_id="GW-M1",
        amount=2000.0,
        transaction_date=date(2026, 8, 20),
        payment_reference="REF-M1",
        net_settlement=2000.0,
        normalized_amount=2000.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="refm1",
        customer_name="Acme Corp",
        normalized_customer="acme corp",
    ))
    test_db.add(BankTransaction(
        bank_txn_id="BNK-M1",
        amount=2000.0,
        transaction_date=date(2026, 8, 20),
        reference="REF-M1",
        normalized_amount=2000.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="refm1",
        description="Customer settlement",
        normalized_desc="customer settlement",
    ))

    # 2. Unmatched Invoice (Missing Gateway)
    test_db.add(Invoice(
        invoice_id="INV-ORPHAN",
        amount=3500.0,
        invoice_date=date(2026, 8, 22),
        invoice_reference="REF-ORPHAN",
        normalized_amount=3500.0,
        normalized_date=date(2026, 8, 22),
        normalized_ref="reforphan",
        customer_name="Beta LLC",
        normalized_customer="beta llc",
    ))

    # 3. Gateway with Missing Bank Settlement
    test_db.add(Invoice(
        invoice_id="INV-UNSETTLED",
        amount=1800.0,
        invoice_date=date(2026, 8, 22),
        invoice_reference="REF-UNSETTLED",
        normalized_amount=1800.0,
        normalized_date=date(2026, 8, 22),
        normalized_ref="refunsettled",
        customer_name="Gamma Inc",
        normalized_customer="gamma inc",
    ))
    test_db.add(GatewayTransaction(
        gateway_txn_id="GW-UNSETTLED",
        amount=1800.0,
        transaction_date=date(2026, 8, 22),
        payment_reference="REF-UNSETTLED",
        net_settlement=1800.0,
        normalized_amount=1800.0,
        normalized_date=date(2026, 8, 22),
        normalized_ref="refunsettled",
        customer_name="Gamma Inc",
        normalized_customer="gamma inc",
    ))

    # 4. Duplicate Invoices
    test_db.add(Invoice(
        invoice_id="INV-DUP-A",
        amount=500.0,
        invoice_date=date(2026, 8, 23),
        invoice_reference="DUP-TOKEN",
        customer_name="Delta Co",
        normalized_customer="delta co",
        normalized_amount=500.0,
        normalized_date=date(2026, 8, 23),
        normalized_ref="duptoken",
        raw_row_hash="hash_dup_500",
    ))
    test_db.add(Invoice(
        invoice_id="INV-DUP-B",
        amount=500.0,
        invoice_date=date(2026, 8, 23),
        invoice_reference="DUP-TOKEN",
        customer_name="Delta Co",
        normalized_customer="delta co",
        normalized_amount=500.0,
        normalized_date=date(2026, 8, 23),
        normalized_ref="duptoken",
        raw_row_hash="hash_dup_500",
    ))

    test_db.commit()

    # Run full reconciliation pipeline
    run = asyncio.run(engine.run_reconciliation(db=test_db, use_ai=False))

    assert run.status == "COMPLETED"
    assert run.matched_count >= 1
    assert run.exception_count >= 1
    assert run.duplicate_count >= 1
    assert run.processing_time_ms > 0
    assert run.throughput_rps > 0

    # Verify Matches
    matches = test_db.query(Match).filter_by(run_id=run.run_id).all()
    assert any(m.invoice_id == "INV-M1" and m.decision == "MATCH" for m in matches)
    for m in matches:
        assert m.evidence_json is not None
        assert m.match_type in ("EXACT", "FUZZY", "MANY_TO_ONE", "SETTLEMENT", "MISSING_BANK_SETTLEMENT", "FEE_RECONCILED", "TIMING_DIFFERENCE")

    # Verify Exceptions
    exceptions = test_db.query(ExceptionRecord).filter_by(run_id=run.run_id).all()
    assert len(exceptions) > 0
    exc_types = {e.exception_type for e in exceptions}
    assert "MISSING_GATEWAY_TRANSACTION" in exc_types or "MISSING_BANK_SETTLEMENT" in exc_types

    for e in exceptions:
        assert e.evidence_json is not None
        assert e.related_records_json is not None

    # Verify Audit Logs
    audit_entries = test_db.query(AuditLog).all()
    assert len(audit_entries) >= len(matches) + len(exceptions)
