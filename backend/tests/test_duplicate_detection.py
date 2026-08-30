"""
Automated Test Suite for Duplicate Transaction Detection (Phase 6).

Problem Solved:
Tests internal and cross-source duplicate transaction detection across Bank,
Payment Gateway, and Invoice datasets, verifying collision grouping, hash fingerprinting,
and structured evidence creation.

Tests:
1. Duplicate detection in BankTransactions (hash and tuple-based).
2. Duplicate detection in GatewayTransactions (double charges).
3. Duplicate detection in Invoices (duplicate billing).
4. Structured evidence serialization and policy citation verification.
5. End-to-end duplicate exception recording in ReconciliationEngine.
"""

import json
import asyncio
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.models.exception import ExceptionRecord
from app.services.reconciliation.duplicate_detector import DuplicateDetector
from app.services.reconciliation.engine import ReconciliationEngine


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_dup.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_bank_duplicate_detection_by_hash_and_fingerprint():
    """
    Tests that DuplicateDetector identifies duplicate bank statement line items.
    """
    b1 = BankTransaction(
        bank_txn_id="BNK-DUP-01",
        amount=5000.0,
        transaction_date=date(2026, 8, 20),
        reference="REF-DUP-100",
        raw_row_hash="hash_bank_dup_100",
    )
    b2 = BankTransaction(
        bank_txn_id="BNK-DUP-02",
        amount=5000.0,
        transaction_date=date(2026, 8, 20),
        reference="REF-DUP-100",
        raw_row_hash="hash_bank_dup_100",
    )
    b_unique = BankTransaction(
        bank_txn_id="BNK-UNIQ-01",
        amount=2500.0,
        transaction_date=date(2026, 8, 20),
        reference="REF-UNIQ-200",
        raw_row_hash="hash_bank_uniq_200",
    )

    dup_groups = DuplicateDetector.detect_duplicates([b1, b2, b_unique], "BANK")
    assert len(dup_groups) == 1

    group = dup_groups[0]
    assert group["source_type"] == "BANK"
    assert group["count"] == 2
    assert group["primary_record"].bank_txn_id == "BNK-DUP-01"
    assert len(group["duplicate_records"]) == 1
    assert group["duplicate_records"][0].bank_txn_id == "BNK-DUP-02"

    evidence = json.loads(group["evidence_json"])
    assert evidence["exception_type"] == "DUPLICATE_TRANSACTION"
    assert evidence["amounts"]["unit_amount"] == 5000.0
    assert evidence["amounts"]["total_duplicated_amount"] == 5000.0
    assert "Anti-Double-Billing" in evidence["policy_citation"]


def test_gateway_duplicate_detection_double_capture():
    """
    Tests duplicate detection for accidental gateway double-charge captures.
    """
    g1 = GatewayTransaction(
        gateway_txn_id="GW-DUP-A",
        amount=1250.0,
        transaction_date=date(2026, 8, 21),
        payment_reference="ORD-PAY-999",
        normalized_amount=1250.0,
        normalized_date=date(2026, 8, 21),
        normalized_ref="ordpay999",
    )
    g2 = GatewayTransaction(
        gateway_txn_id="GW-DUP-B",
        amount=1250.0,
        transaction_date=date(2026, 8, 21),
        payment_reference="ORD-PAY-999",
        normalized_amount=1250.0,
        normalized_date=date(2026, 8, 21),
        normalized_ref="ordpay999",
    )

    dup_groups = DuplicateDetector.detect_duplicates([g1, g2], "GATEWAY")
    assert len(dup_groups) == 1
    assert dup_groups[0]["count"] == 2
    assert dup_groups[0]["primary_record"].gateway_txn_id == "GW-DUP-A"
    assert dup_groups[0]["duplicate_records"][0].gateway_txn_id == "GW-DUP-B"


def test_invoice_duplicate_detection_triple_billing():
    """
    Tests duplicate detection when an invoice is billed 3 times.
    """
    inv1 = Invoice(
        invoice_id="INV-TRIP-1",
        amount=750.0,
        invoice_date=date(2026, 8, 22),
        invoice_reference="INV-REF-777",
        raw_row_hash="hash777",
    )
    inv2 = Invoice(
        invoice_id="INV-TRIP-2",
        amount=750.0,
        invoice_date=date(2026, 8, 22),
        invoice_reference="INV-REF-777",
        raw_row_hash="hash777",
    )
    inv3 = Invoice(
        invoice_id="INV-TRIP-3",
        amount=750.0,
        invoice_date=date(2026, 8, 22),
        invoice_reference="INV-REF-777",
        raw_row_hash="hash777",
    )

    dup_groups = DuplicateDetector.detect_duplicates([inv1, inv2, inv3], "INVOICE")
    assert len(dup_groups) == 1
    assert dup_groups[0]["count"] == 3
    assert dup_groups[0]["primary_record"].invoice_id == "INV-TRIP-1"
    assert len(dup_groups[0]["duplicate_records"]) == 2


def test_engine_registers_duplicate_exceptions(test_db):
    """
    Tests that the reconciliation engine flags duplicate records as DUPLICATE_TRANSACTION exceptions.
    """
    # Add unique invoice
    test_db.add(Invoice(
        invoice_id="INV-VALID",
        amount=2000.0,
        invoice_date=date(2026, 8, 20),
        invoice_reference="REF-V1",
        normalized_amount=2000.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="refv1",
        customer_name="Acme Corp",
        normalized_customer="acme corp",
    ))

    # Add duplicate gateway records (2 captures for same reference)
    test_db.add(GatewayTransaction(
        gateway_txn_id="GW-DUP-1",
        amount=2000.0,
        transaction_date=date(2026, 8, 20),
        payment_reference="REF-V1",
        normalized_amount=2000.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="refv1",
        customer_name="Acme Corp",
        normalized_customer="acme corp",
        raw_row_hash="gw_dup_hash_v1",
    ))
    test_db.add(GatewayTransaction(
        gateway_txn_id="GW-DUP-2",
        amount=2000.0,
        transaction_date=date(2026, 8, 20),
        payment_reference="REF-V1",
        normalized_amount=2000.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="refv1",
        customer_name="Acme Corp",
        normalized_customer="acme corp",
        raw_row_hash="gw_dup_hash_v1",
    ))

    # Add bank transaction
    test_db.add(BankTransaction(
        bank_txn_id="BNK-V1",
        amount=2000.0,
        transaction_date=date(2026, 8, 20),
        reference="REF-V1",
        normalized_amount=2000.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="refv1",
        description="Customer settlement",
        normalized_desc="customer settlement",
    ))

    test_db.commit()

    engine = ReconciliationEngine()
    run = asyncio.run(engine.run_reconciliation(db=test_db, use_ai=False))

    assert run.status == "COMPLETED"
    assert run.duplicate_count >= 1

    exceptions = test_db.query(ExceptionRecord).filter_by(run_id=run.run_id).all()
    dup_exceptions = [e for e in exceptions if e.exception_type == "DUPLICATE_TRANSACTION"]
    assert len(dup_exceptions) >= 1
    de = dup_exceptions[0]
    assert de.severity == "HIGH"
    assert de.evidence_json is not None
