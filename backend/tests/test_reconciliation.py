"""
Integration tests for the Reconciliation Pipeline.
"""

import asyncio
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.ingestion import IngestionService
from app.services.reconciliation import ReconciliationService
from scripts.generate_dataset import generate_synthetic_data


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_reconcile.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_full_reconciliation_pipeline(test_db, tmp_path):
    # 1. Generate test dataset with 50 records
    data_dir = str(tmp_path / "data")
    gen_res = generate_synthetic_data(count=50, seed=123, output_dir=data_dir)

    # 2. Ingest datasets
    IngestionService.ingest_bank_transactions(test_db, gen_res["bank_path"])
    IngestionService.ingest_gateway_transactions(test_db, gen_res["gateway_path"])
    IngestionService.ingest_invoices(test_db, gen_res["invoice_path"])

    # 3. Execute reconciliation synchronously via asyncio.run
    service = ReconciliationService()
    run = asyncio.run(
        service.run_reconciliation(
            db=test_db,
            use_ai=True,
            ground_truth_path=gen_res["ground_truth_path"],
        )
    )

    assert run.status == "COMPLETED"
    assert run.total_records > 0
    assert run.matched_count > 0
    assert run.throughput_rps > 0.0
    assert len(run.matches) > 0
