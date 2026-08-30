import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.reconciliation import ReconciliationRun, Match
from app.models.exception import ExceptionRecord
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.models.dataset import Dataset, FileRecord

@pytest.fixture
def reset_client(tmp_path):
    db_file = tmp_path / "test_reset.db"
    test_engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as tc:
        # Seed test data
        db = TestingSessionLocal()
        db.add(BankTransaction(
            bank_txn_id="B1",
            transaction_date=date(2026, 3, 1),
            amount=1000.0,
            description="Test",
            reference="REF1",
            normalized_amount=1000.0,
            normalized_date=date(2026, 3, 1),
            normalized_ref="REF1",
            normalized_desc="test"
        ))
        db.add(GatewayTransaction(
            gateway_txn_id="G1",
            transaction_date=date(2026, 3, 1),
            amount=1000.0,
            customer_name="Cust",
            payment_reference="REF1",
            normalized_amount=1000.0,
            normalized_date=date(2026, 3, 1),
            normalized_ref="REF1",
            normalized_customer="cust"
        ))
        db.add(Invoice(
            invoice_id="I1",
            invoice_date=date(2026, 3, 1),
            customer_name="Cust",
            amount=1000.0,
            invoice_reference="REF1",
            normalized_amount=1000.0,
            normalized_date=date(2026, 3, 1),
            normalized_ref="REF1",
            normalized_customer="cust"
        ))
        db.add(ReconciliationRun(
            run_id="RUN_TEST",
            status="COMPLETED",
            total_records=3
        ))
        db.add(Match(
            match_id="M1",
            run_id="RUN_TEST",
            decision="MATCH",
            confidence_score=1.0,
            explanation="Test match"
        ))
        db.add(ExceptionRecord(
            exception_id="E1",
            run_id="RUN_TEST",
            exception_type="AMOUNT_MISMATCH",
            explanation="Test exception",
            recommended_action="Review"
        ))
        db.commit()
        db.close()

        yield tc, TestingSessionLocal

    app.dependency_overrides.pop(get_db, None)


def test_reset_reconciliation_endpoint(reset_client):
    tc, SessionFactory = reset_client

    # Verify initial data exists
    db = SessionFactory()
    assert db.query(BankTransaction).count() == 1
    assert db.query(GatewayTransaction).count() == 1
    assert db.query(Invoice).count() == 1
    assert db.query(Match).count() == 1
    assert db.query(ExceptionRecord).count() == 1
    db.close()

    # Call reset endpoint
    res = tc.post("/api/reconciliation/reset")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"

    # Verify all data was completely wiped
    db = SessionFactory()
    assert db.query(BankTransaction).count() == 0
    assert db.query(GatewayTransaction).count() == 0
    assert db.query(Invoice).count() == 0
    assert db.query(Match).count() == 0
    assert db.query(ExceptionRecord).count() == 0
    assert db.query(ReconciliationRun).count() == 0
    db.close()

    # Verify API endpoints return 0 items
    tx_res = tc.get("/api/transactions")
    assert tx_res.status_code == 200
    assert tx_res.json()["total"] == 0
    assert len(tx_res.json()["items"]) == 0

    exc_res = tc.get("/api/exceptions")
    assert exc_res.status_code == 200
    assert exc_res.json()["total"] == 0
    assert len(exc_res.json()["items"]) == 0
