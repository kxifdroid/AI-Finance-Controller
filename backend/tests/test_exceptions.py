"""
Unit and integration tests for ExceptionService.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.services.exceptions import ExceptionService


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_exc.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_exception_lifecycle_workflow(test_db):
    # 1. Create an exception record
    exc = ExceptionService.classify_and_create_exception(
        db=test_db,
        run_id="TEST_RUN_1",
        bank_record=None,
        gateway_record=None,
        invoice_record=None,
        decision="EXCEPTION",
        reason="Fee mismatch of 500 currency units",
        recommended_action="Review gateway fee schedule",
        suggested_type="AMOUNT_MISMATCH",
        suggested_severity="HIGH",
    )
    test_db.commit()

    assert exc.exception_id.startswith("EXC_")
    assert exc.status == "OPEN"
    assert exc.severity == "HIGH"

    # 2. Transition to IN_REVIEW
    updated = ExceptionService.update_exception_status(
        db=test_db,
        exception_id=exc.exception_id,
        status="IN_REVIEW",
        notes="Operator investigating fee report",
        resolved_by="Auditor_John",
    )
    assert updated.status == "IN_REVIEW"
    assert updated.notes == "Operator investigating fee report"

    # 3. Resolve
    resolved = ExceptionService.update_exception_status(
        db=test_db,
        exception_id=exc.exception_id,
        status="RESOLVED",
        notes="Fee difference adjusted in journal",
    )
    assert resolved.status == "RESOLVED"


def test_four_exception_categories(test_db):
    # Case 1: TIMING_DIFFERENCE
    exc_timing = ExceptionService.classify_and_create_exception(
        db=test_db,
        run_id="RUN_TEST",
        bank_record=None,
        gateway_record=None,
        invoice_record=None,
        decision="EXCEPTION",
        reason="Date fell outside 5 day window",
        recommended_action="Review settlement lag",
        is_timing_difference=True,
    )
    assert exc_timing.exception_type == "TIMING_DIFFERENCE"

    # Case 2: FEE_VARIANCE (e.g. Bank 9,764 vs Gateway 10,000 = 2.36% fee)
    mock_bank = BankTransaction(bank_txn_id="B_1", amount=9764.0)
    mock_gw = GatewayTransaction(gateway_txn_id="G_1", amount=10000.0)
    exc_fee = ExceptionService.classify_and_create_exception(
        db=test_db,
        run_id="RUN_TEST",
        bank_record=mock_bank,
        gateway_record=mock_gw,
        invoice_record=None,
        decision="EXCEPTION",
        reason="",
        recommended_action="",
    )
    assert exc_fee.exception_type == "FEE_VARIANCE"
    assert "2.36%" in exc_fee.explanation

    # Case 3: AMOUNT_MISMATCH (e.g. Invoice 15,000 vs Gateway 10,000 = 5,000 underpayment)
    mock_inv = Invoice(invoice_id="INV_1", amount=15000.0)
    mock_gw_partial = GatewayTransaction(gateway_txn_id="G_2", amount=10000.0)
    exc_amt = ExceptionService.classify_and_create_exception(
        db=test_db,
        run_id="RUN_TEST",
        bank_record=None,
        gateway_record=mock_gw_partial,
        invoice_record=mock_inv,
        decision="EXCEPTION",
        reason="",
        recommended_action="",
    )
    assert exc_amt.exception_type == "AMOUNT_MISMATCH"
    assert "5,000" in exc_amt.explanation or "5000" in exc_amt.explanation

    # Case 4: NO_MATCH_FOUND (e.g. orphan Bank transaction)
    mock_bank_orphan = BankTransaction(bank_txn_id="B_ORPHAN", amount=500.0)
    exc_missing = ExceptionService.classify_and_create_exception(
        db=test_db,
        run_id="RUN_TEST",
        bank_record=mock_bank_orphan,
        gateway_record=None,
        invoice_record=None,
        decision="MISSING",
        reason="",
        recommended_action="",
    )
    assert exc_missing.exception_type == "NO_MATCH_FOUND"
    assert "Gateway" in exc_missing.explanation and "Invoice" in exc_missing.explanation
