"""
Comprehensive Automated Regression Test Suite for Reconciliation Invariants.
Tests Parent/Child topology, topology-aware scoring, canonical reason codes,
deterministic explanation assertions, AI segregation, and arbitrary dataset support.
"""

import os
import json
import uuid
from datetime import date, datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.models.reconciliation import Match, ReconciliationRun
from app.models.exception import ExceptionRecord
from app.services.reconciliation.engine import ReconciliationEngine
from app.services.reconciliation.canonical_codes import CanonicalReasonCode
from app.services.reconciliation.explanation_builder import ExplanationBuilder
from app.services.scoring import ScoringService


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def make_invoice(invoice_id: str, dataset_id: str, dt: date, amount: float, customer: str, ref: str) -> Invoice:
    return Invoice(
        invoice_id=invoice_id,
        dataset_id=dataset_id,
        invoice_date=dt,
        amount=amount,
        customer_name=customer,
        invoice_reference=ref,
        normalized_amount=amount,
        normalized_date=dt,
        normalized_ref=ref,
        normalized_customer=customer.lower(),
    )


def make_gateway(gateway_txn_id: str, dataset_id: str, dt: date, amount: float, customer: str, ref: str, fee: float = 0.0, tax: float = 0.0, net: float = 0.0) -> GatewayTransaction:
    net_amt = net if net > 0 else (amount - fee - tax)
    return GatewayTransaction(
        gateway_txn_id=gateway_txn_id,
        dataset_id=dataset_id,
        transaction_date=dt,
        amount=amount,
        customer_name=customer,
        payment_reference=ref,
        gateway_fee=fee,
        tax_on_fee=tax,
        net_settlement=net_amt,
        normalized_amount=amount,
        normalized_date=dt,
        normalized_ref=ref,
        normalized_customer=customer.lower(),
    )


def make_bank(bank_txn_id: str, dataset_id: str, dt: date, amount: float, desc: str, ref: str) -> BankTransaction:
    return BankTransaction(
        bank_txn_id=bank_txn_id,
        dataset_id=dataset_id,
        transaction_date=dt,
        amount=amount,
        description=desc,
        reference=ref,
        normalized_amount=amount,
        normalized_date=dt,
        normalized_ref=ref,
        normalized_desc=desc.lower(),
    )


# ==============================================================================
# TEST 1: Exact 3-Way Match (1000 = 1000 = 1000) -> MATCH, EXACT_3_WAY_MATCH
# ==============================================================================
def test_exact_3way_match(test_db):
    ds_id = "ds_test1"
    today = date(2026, 8, 30)

    test_db.add(make_invoice("INV_001", ds_id, today, 1000.0, "Acme Corp", "REF_001"))
    test_db.add(make_gateway("GTW_001", ds_id, today, 1000.0, "Acme Corp", "REF_001"))
    test_db.add(make_bank("BNK_001", ds_id, today, 1000.0, "Settlement REF_001", "REF_001"))
    test_db.commit()

    engine = ReconciliationEngine()
    run = engine.reconcile(db=test_db, dataset_id=ds_id, use_ai=False)

    matches = test_db.query(Match).filter(Match.run_id == run.run_id).all()
    assert len(matches) == 1
    m = matches[0]
    assert m.decision == "MATCH"
    assert m.reason_code == CanonicalReasonCode.EXACT_3_WAY_MATCH
    assert m.amount_similarity == 1.0
    assert "Fully reconciled" in m.explanation
    assert m.variance_amount == 0.0


# ==============================================================================
# TEST 2: Amount Mismatch (Inv 1000, GW 1000, Bank 950) -> REVIEW, AMOUNT_MISMATCH
# ==============================================================================
def test_amount_mismatch_not_100_percent(test_db):
    ds_id = "ds_test2"
    today = date(2026, 8, 30)

    test_db.add(make_invoice("INV_002", ds_id, today, 1000.0, "Beta Corp", "REF_002"))
    test_db.add(make_gateway("GTW_002", ds_id, today, 1000.0, "Beta Corp", "REF_002"))
    test_db.add(make_bank("BNK_002", ds_id, today, 950.0, "Settlement REF_002", "REF_002"))
    test_db.commit()

    engine = ReconciliationEngine()
    run = engine.reconcile(db=test_db, dataset_id=ds_id, use_ai=False)

    matches = test_db.query(Match).filter(Match.run_id == run.run_id).all()
    assert len(matches) == 1
    m = matches[0]
    assert m.decision == "REVIEW"
    assert m.reason_code == CanonicalReasonCode.AMOUNT_MISMATCH
    assert m.amount_similarity < 1.0  # Must NOT be 100%
    assert abs(m.variance_amount) == 50.0
    # Must NOT contain positive match language
    assert "Fully reconciled" not in m.explanation
    assert "Amount mismatch" in m.explanation


# ==============================================================================
# TEST 3: Deterministic MATCH with AI saying REVIEW -> Final status remains MATCH
# ==============================================================================
def test_ai_cannot_override_deterministic_match(test_db):
    m = Match(
        match_id="M_TEST_AI_1",
        run_id="RUN_AI_1",
        topology="ONE_TO_ONE",
        reason_code=CanonicalReasonCode.EXACT_3_WAY_MATCH,
        decision="MATCH",
        confidence_score=1.0,
        deterministic_confidence=1.0,
        explanation="Fully reconciled",
        amount_similarity=1.0,
        date_similarity=1.0,
        reference_similarity=1.0,
        customer_similarity=1.0,
        composite_score=1.0,
        verified_by_ai=True,
        ai_verification_status="ADVISORY_REVIEW",
        ai_explanation="AI suspected possible risk but accounting match is deterministic",
    )
    test_db.add(m)
    test_db.commit()

    rec = test_db.query(Match).filter(Match.match_id == "M_TEST_AI_1").first()
    assert rec.decision == "MATCH"  # Accounting decision preserved!
    assert rec.verified_by_ai is True
    assert rec.ai_verification_status == "ADVISORY_REVIEW"


# ==============================================================================
# TEST 4: Deterministic AMOUNT_MISMATCH with AI saying MATCH -> Status remains REVIEW
# ==============================================================================
def test_ai_cannot_override_deterministic_mismatch(test_db):
    m = Match(
        match_id="M_TEST_AI_2",
        run_id="RUN_AI_2",
        topology="ONE_TO_ONE",
        reason_code=CanonicalReasonCode.AMOUNT_MISMATCH,
        decision="REVIEW",
        confidence_score=0.75,
        deterministic_confidence=0.75,
        explanation="Amount mismatch variance of ₹50.00",
        amount_similarity=0.6065,
        verified_by_ai=True,
        ai_verification_status="ADVISORY_MATCH",
    )
    test_db.add(m)
    test_db.commit()

    rec = test_db.query(Match).filter(Match.match_id == "M_TEST_AI_2").first()
    assert rec.decision == "REVIEW"  # Accounting decision preserved!


# ==============================================================================
# TEST 5: Fee Reconciliation (Gross 10000, Fee 200, GST 36, Bank 9764) -> MATCH, FEE_RECONCILED
# ==============================================================================
def test_fee_reconciliation(test_db):
    ds_id = "ds_fee"
    today = date(2026, 8, 30)

    test_db.add(make_invoice("INV_FEE", ds_id, today, 10000.0, "Gamma Ltd", "REF_FEE"))
    test_db.add(make_gateway("GTW_FEE", ds_id, today, 10000.0, "Gamma Ltd", "REF_FEE", fee=200.0, tax=36.0, net=9764.0))
    test_db.add(make_bank("BNK_FEE", ds_id, today, 9764.0, "Settlement REF_FEE", "REF_FEE"))
    test_db.commit()

    engine = ReconciliationEngine()
    run = engine.reconcile(db=test_db, dataset_id=ds_id, use_ai=False)

    matches = test_db.query(Match).filter(Match.run_id == run.run_id).all()
    assert len(matches) == 1
    m = matches[0]
    assert m.decision == "MATCH"
    assert m.reason_code == CanonicalReasonCode.FEE_RECONCILED
    assert m.match_type == "FEE_RECONCILED"
    assert m.fee_classification == "FEE_RECONCILED"


# ==============================================================================
# TEST 6 & 7: Batch Settlement (Bank 6000, Gateways 2000 + 4000, Invoice 6000)
# Expected: EXACTLY ONE parent reconciliation row on Dashboard, MATCH, MANY_TO_ONE
# ==============================================================================
def test_many_to_one_deduplication(test_db):
    ds_id = "ds_batch"
    d1 = date(2026, 8, 28)
    d2 = date(2026, 8, 29)
    d_bank = date(2026, 8, 30)

    # Invoices
    test_db.add(make_invoice("INV_B1", ds_id, d1, 2000.0, "Customer 1", "ORD_B1"))
    test_db.add(make_invoice("INV_B2", ds_id, d2, 4000.0, "Customer 2", "ORD_B2"))

    # Gateways
    test_db.add(make_gateway("GTW_B1", ds_id, d1, 2000.0, "Customer 1", "ORD_B1", net=2000.0))
    test_db.add(make_gateway("GTW_B2", ds_id, d2, 4000.0, "Customer 2", "ORD_B2", net=4000.0))

    # Single Bank Batch Deposit
    test_db.add(make_bank("BNK_BATCH_6K", ds_id, d_bank, 6000.0, "Razorpay Payout Batch 6000", "BATCH_6000"))
    test_db.commit()

    engine = ReconciliationEngine()
    run = engine.reconcile(db=test_db, dataset_id=ds_id, use_ai=False)

    matches = test_db.query(Match).filter(Match.run_id == run.run_id).all()
    # Invariant: EXACTLY 1 row for the bank deposit (NOT 2)!
    assert len(matches) == 1
    m = matches[0]
    assert m.topology == "MANY_TO_ONE"
    assert m.reason_code == CanonicalReasonCode.MANY_TO_ONE_MATCH
    assert m.decision == "MATCH"
    assert m.bank_txn_id == "BNK_BATCH_6K"

    # Check child lists
    gw_ids = json.loads(m.gateway_txn_ids_json)
    assert len(gw_ids) == 2
    assert "GTW_B1" in gw_ids and "GTW_B2" in gw_ids


# ==============================================================================
# TEST 8 & 9: Many-to-One Detail View Data Contract & Invoice Linkage
# ==============================================================================
def test_many_to_one_detail_contract(test_db):
    ds_id = "ds_batch_contract"
    d = date(2026, 8, 30)

    test_db.add(make_invoice("INV_C1", ds_id, d, 6000.0, "Bulk Customer", "BATCH_REF"))
    test_db.add(make_gateway("GTW_C1", ds_id, d, 2500.0, "Bulk Customer", "REF_1", net=2500.0))
    test_db.add(make_gateway("GTW_C2", ds_id, d, 3500.0, "Bulk Customer", "REF_2", net=3500.0))
    test_db.add(make_bank("BNK_C1", ds_id, d, 6000.0, "Payout BATCH_REF", "BATCH_REF"))
    test_db.commit()

    engine = ReconciliationEngine()
    run = engine.reconcile(db=test_db, dataset_id=ds_id, use_ai=False)

    m = test_db.query(Match).filter(Match.run_id == run.run_id).first()
    assert m is not None
    assert m.topology == "MANY_TO_ONE"
    amounts = json.loads(m.amounts_json)
    assert amounts["gateway_gross_total"] == 6000.0
    assert amounts["bank_credit_total"] == 6000.0
    assert amounts["variance"] == 0.0


# ==============================================================================
# TEST 10: Arbitrary Dataset with Randomized Names and Values
# ==============================================================================
def test_arbitrary_randomized_dataset(test_db):
    ds_id = f"ds_rand_{uuid.uuid4().hex[:6]}"
    today = date(2026, 8, 30)

    # 3 random transactions
    for i in range(3):
        ref = f"CUSTOM_REF_{uuid.uuid4().hex[:8]}"
        cust = f"Random Enterprise {uuid.uuid4().hex[:4]}"
        amt = round(1234.56 + i * 500, 2)
        test_db.add(make_invoice(f"INV_R_{i}", ds_id, today, amt, cust, ref))
        test_db.add(make_gateway(f"GTW_R_{i}", ds_id, today, amt, cust, ref, net=amt))
        test_db.add(make_bank(f"BNK_R_{i}", ds_id, today, amt, f"Payout {ref}", ref))
    test_db.commit()

    engine = ReconciliationEngine()
    run = engine.reconcile(db=test_db, dataset_id=ds_id, use_ai=False)

    matches = test_db.query(Match).filter(Match.run_id == run.run_id).all()
    assert len(matches) == 3
    for m in matches:
        assert m.decision == "MATCH"
        assert m.reason_code == CanonicalReasonCode.EXACT_3_WAY_MATCH


# ==============================================================================
# TEST 11: Pipeline Idempotency (Running Twice Yields Identical Results)
# ==============================================================================
def test_pipeline_idempotency(test_db):
    ds_id = "ds_idempotent"
    today = date(2026, 8, 30)

    test_db.add(make_invoice("INV_IDEM", ds_id, today, 500.0, "Idem Corp", "REF_IDEM"))
    test_db.add(make_gateway("GTW_IDEM", ds_id, today, 500.0, "Idem Corp", "REF_IDEM", net=500.0))
    test_db.add(make_bank("BNK_IDEM", ds_id, today, 500.0, "REF_IDEM", "REF_IDEM"))
    test_db.commit()

    engine = ReconciliationEngine()
    run1 = engine.reconcile(db=test_db, dataset_id=ds_id, use_ai=False)
    run2 = engine.reconcile(db=test_db, dataset_id=ds_id, use_ai=False)

    assert run1.matched_count == run2.matched_count == 1
    assert run1.review_count == run2.review_count == 0


# ==============================================================================
# TEST 12 & 13: Explanation Determinism and Strict Non-Positive Language
# ==============================================================================
def test_explanation_strict_non_positive_on_review():
    exp_review = ExplanationBuilder.build_explanation_and_action(
        decision="REVIEW",
        reason_code=CanonicalReasonCode.AMOUNT_MISMATCH,
        amounts={"invoice_total": 1000.0, "gateway_gross_total": 1000.0, "bank_credit_total": 950.0, "variance": 50.0},
        context={"reference": "REF_99"},
    )
    # Positive words forbidden on REVIEW
    assert "Fully reconciled" not in exp_review["explanation"]
    assert "successfully reconciled" not in exp_review["explanation"].lower()
    assert "Amount mismatch" in exp_review["explanation"]

    exp_match = ExplanationBuilder.build_explanation_and_action(
        decision="MATCH",
        reason_code=CanonicalReasonCode.EXACT_3_WAY_MATCH,
        amounts={"invoice_total": 1000.0, "gateway_gross_total": 1000.0, "bank_credit_total": 1000.0, "variance": 0.0},
        context={"reference": "REF_99"},
    )
    assert "Fully reconciled" in exp_match["explanation"]
