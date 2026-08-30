"""
Automated Test Suite for Fee and Tax Reconciliation (Phase 6).

Problem Solved:
Tests exact mathematical MDR fee calculations (10,000 - 200 - 36 = 9,764),
18% GST tax decomposition, contractual variance tolerances, and fee mismatch detection.

Tests:
1. Mathematical fee settlement formula: gross - fee - tax = net.
2. 18% GST calculation on gateway processing fee.
3. Variance validation: FEE_RECONCILED, FEE_VARIANCE (1%-5%), and FEE_MISMATCH (>5%).
4. ExactMatcher Leg 2 fee variance resolution.
5. ExceptionService classification for fee variance vs fee mismatch.
"""

import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.services.reconciliation.fee_calculator import FeeCalculator
from app.services.reconciliation.exact_matcher import ExactMatcher
from app.services.exceptions import ExceptionService
from app.config import settings


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_fee.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_standard_razorpay_fee_gst_formula():
    """
    Tests the canonical 10,000 - 200 - 36 = 9,764 fee + GST reconciliation.
    - Gross: ₹10,000.00
    - Base MDR Fee (2.0%): ₹200.00
    - GST on Fee (18.0% of 200): ₹36.00
    - Net Bank Settlement: ₹9,764.00
    """
    gross = 10000.0
    fee_rate = 0.02
    fee = round(gross * fee_rate, 2)
    assert fee == 200.0

    gst = FeeCalculator.calculate_gst_on_fee(fee)
    assert gst == 36.0

    net = FeeCalculator.calculate_fee_settlement(
        gross_amount=gross,
        fee_amount=fee,
        tax_amount=gst,
    )
    assert net == 9764.0
    assert gross - fee - gst == net


def test_fee_calculator_validate_variance_scenarios():
    """
    Tests various fee variance evaluation outcomes:
    1. Exact breakdown match -> FEE_RECONCILED
    2. Implied 2.36% fee -> FEE_VARIANCE
    3. Implied 2.0% fee -> FEE_VARIANCE
    4. Excessive 10.0% fee -> FEE_MISMATCH
    5. Zero fee (exact gross match) -> FEE_RECONCILED
    """
    gross = 10000.0

    # 1. Exact reconciliation with explicit fee and tax
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

    # 2. Implied fee without breakdown (9,764 credited)
    is_valid, fee_pct, variance, classification = FeeCalculator.validate_fee_variance(
        gross_amount=gross,
        actual_bank_credit=9764.0,
    )
    assert is_valid is True
    assert classification == "FEE_VARIANCE"
    assert fee_pct == 0.0236
    assert variance == 236.0

    # 3. Implied fee (9,800 credited = 2.0% fee)
    is_valid, fee_pct, variance, classification = FeeCalculator.validate_fee_variance(
        gross_amount=gross,
        actual_bank_credit=9800.0,
    )
    assert is_valid is True
    assert classification == "FEE_VARIANCE"
    assert fee_pct == 0.02
    assert variance == 200.0

    # 4. Excessive fee deduction (9,000 credited = 10.0% deduction, exceeds 5% max)
    is_valid, fee_pct, variance, classification = FeeCalculator.validate_fee_variance(
        gross_amount=gross,
        actual_bank_credit=9000.0,
    )
    assert is_valid is False
    assert classification == "FEE_MISMATCH"
    assert fee_pct == 0.10
    assert variance == 1000.0

    # 5. Exact match with 0 fee (10,000 credited)
    is_valid, fee_pct, variance, classification = FeeCalculator.validate_fee_variance(
        gross_amount=gross,
        actual_bank_credit=10000.0,
    )
    assert is_valid is True
    assert classification == "FEE_RECONCILED"
    assert fee_pct == 0.0
    assert variance == 0.0


def test_exact_matcher_leg2_with_fee_variance():
    """
    Tests that Leg 2 (Gateway ↔ Bank) matches transactions with fee variance
    when allow_fee_variance=True.
    """
    gw = GatewayTransaction(
        gateway_txn_id="GW-FEE-TEST-1",
        amount=10000.0,
        gross_amount=10000.0,
        gateway_fee=200.0,
        tax_on_fee=36.0,
        net_settlement=9764.0,
        transaction_date=date(2026, 8, 20),
        payment_reference="ORD-FEE-1",
        normalized_amount=10000.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="ordfee1",
    )

    bank = BankTransaction(
        bank_txn_id="BNK-FEE-TEST-1",
        amount=9764.0,
        transaction_date=date(2026, 8, 20),
        reference="ORD-FEE-1",
        normalized_amount=9764.0,
        normalized_date=date(2026, 8, 20),
        normalized_ref="ordfee1",
        description="Razorpay Net Settlement",
    )

    matched, rem_a, rem_b, matched_a, matched_b = ExactMatcher.match(
        side_a_records=[gw],
        side_b_records=[bank],
        leg_name="Leg 2: Gateway ↔ Bank",
        allow_fee_variance=True,
    )

    assert len(matched) == 1
    assert "GW-FEE-TEST-1" in matched_a
    assert "BNK-FEE-TEST-1" in matched_b
    assert len(rem_a) == 0
    assert len(rem_b) == 0

    m = matched[0]
    assert m["match_type"] == "EXACT"
    assert m["amount"] == 9764.0
    assert m["side_a"].amount == 10000.0


def test_exception_service_classifies_fee_variance_and_mismatch(test_db):
    """
    Tests that ExceptionService accurately classifies 2.36% variance as FEE_VARIANCE
    and 10% discrepancy as AMOUNT_MISMATCH.
    """
    # 1. Standard Fee Variance (Gross 10,000, Bank 9,764 -> 2.36% fee)
    gw_std = GatewayTransaction(gateway_txn_id="GW-S1", amount=10000.0)
    bank_std = BankTransaction(bank_txn_id="BNK-S1", amount=9764.0)

    exc_var = ExceptionService.classify_and_create_exception(
        db=test_db,
        run_id="RUN_FEE_TEST",
        bank_record=bank_std,
        gateway_record=gw_std,
        decision="EXCEPTION",
    )
    assert exc_var.exception_type == "FEE_VARIANCE"
    assert exc_var.amount_discrepancy == 236.0
    assert "2.36%" in exc_var.explanation

    # 2. Severe Mismatch (Gross 10,000, Bank 8,000 -> 20% variance)
    gw_sev = GatewayTransaction(gateway_txn_id="GW-S2", amount=10000.0)
    bank_sev = BankTransaction(bank_txn_id="BNK-S2", amount=8000.0)

    exc_mismatch = ExceptionService.classify_and_create_exception(
        db=test_db,
        run_id="RUN_FEE_TEST",
        bank_record=bank_sev,
        gateway_record=gw_sev,
        decision="EXCEPTION",
    )
    assert exc_mismatch.exception_type == "AMOUNT_MISMATCH"
    assert exc_mismatch.amount_discrepancy == 2000.0
    assert exc_mismatch.severity == "MEDIUM" or exc_mismatch.severity == "HIGH"
