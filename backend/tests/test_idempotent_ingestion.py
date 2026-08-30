import pytest
import pandas as pd
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.services.ingestion import IngestionService


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_idempotent.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_bank_ingestion_idempotency(test_db):
    # 1. Create a 3-row bank DataFrame
    df_initial = pd.DataFrame([
        {"bank_txn_id": "BNK-001", "transaction_date": "2026-08-01", "amount": 1000.0, "reference": "REF-100", "description": "Deposit A"},
        {"bank_txn_id": "BNK-002", "transaction_date": "2026-08-02", "amount": 2500.0, "reference": "REF-200", "description": "Deposit B"},
        {"bank_txn_id": "BNK-003", "transaction_date": "2026-08-03", "amount": 5000.0, "reference": "REF-300", "description": "Deposit C"},
    ])

    # First ingestion
    records1, errs1, ingested1, skipped1 = IngestionService.ingest_bank_transactions(test_db, df_initial)
    test_db.commit()

    assert len(records1) == 3
    assert ingested1 == 3
    assert skipped1 == 0
    assert test_db.query(BankTransaction).count() == 3

    # 2. Re-ingest the exact same 3 rows -> Must be a no-op (3 rows stay 3 rows)
    records2, errs2, ingested2, skipped2 = IngestionService.ingest_bank_transactions(test_db, df_initial)
    test_db.commit()

    assert ingested2 == 0
    assert skipped2 == 3
    assert test_db.query(BankTransaction).count() == 3  # Count is still 3, not 6!

    # 3. Ingest a DataFrame with the 3 existing rows PLUS 1 new row
    df_augmented = pd.DataFrame([
        {"bank_txn_id": "BNK-001", "transaction_date": "2026-08-01", "amount": 1000.0, "reference": "REF-100", "description": "Deposit A"},
        {"bank_txn_id": "BNK-002", "transaction_date": "2026-08-02", "amount": 2500.0, "reference": "REF-200", "description": "Deposit B"},
        {"bank_txn_id": "BNK-003", "transaction_date": "2026-08-03", "amount": 5000.0, "reference": "REF-300", "description": "Deposit C"},
        {"bank_txn_id": "BNK-004", "transaction_date": "2026-08-04", "amount": 7500.0, "reference": "REF-400", "description": "Deposit D"},
    ])

    records3, errs3, ingested3, skipped3 = IngestionService.ingest_bank_transactions(test_db, df_augmented)
    test_db.commit()

    assert ingested3 == 1
    assert skipped3 == 3
    assert test_db.query(BankTransaction).count() == 4  # Count is N+1 (4), not 2N+1 or 7!


def test_gateway_ingestion_idempotency_and_net_derivation(test_db):
    df_gw = pd.DataFrame([
        {
            "gateway_txn_id": "GTW-101",
            "transaction_date": "2026-08-01",
            "gross_amount": 1000.0,
            "gateway_fee": 20.0,
            "tax_on_fee": 3.60,
            "payment_reference": "ORD-101",
            "customer_name": "Acme Corp"
        }
    ])

    # First ingestion
    records, errs, ingested, skipped = IngestionService.ingest_gateway_transactions(test_db, df_gw)
    test_db.commit()

    assert ingested == 1
    assert skipped == 0
    saved = test_db.query(GatewayTransaction).first()
    assert saved.gross_amount == 1000.0
    assert saved.net_settlement == 976.40
    assert saved.net_amount_derived is True

    # Re-ingest exact same row
    records2, errs2, ingested2, skipped2 = IngestionService.ingest_gateway_transactions(test_db, df_gw)
    test_db.commit()
    assert ingested2 == 0
    assert skipped2 == 1
    assert test_db.query(GatewayTransaction).count() == 1
