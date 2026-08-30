import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.session import get_db, Base
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.models.reconciliation import ReconciliationRun

TEST_DB_URL = "sqlite:///./test_e2e.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    try:
        if os.path.exists("./test_e2e.db"):
            os.remove("./test_e2e.db")
    except Exception:
        pass

def test_e2e_upload_and_reconciliation():
    db = TestingSessionLocal()
    # 1. Upload files
    with open("data/generated/bank_transactions.csv", "rb") as f:
        res1 = client.post("/api/upload/file", data={"data_type": "BANK"}, files={"file": f})
    assert res1.status_code == 200
    bank_file_id = res1.json()["file_id"]
    
    with open("data/generated/gateway_transactions.csv", "rb") as f:
        res2 = client.post("/api/upload/file", data={"data_type": "GATEWAY"}, files={"file": f})
    gw_file_id = res2.json()["file_id"]
    
    with open("data/generated/invoices.csv", "rb") as f:
        res3 = client.post("/api/upload/file", data={"data_type": "INVOICE"}, files={"file": f})
    inv_file_id = res3.json()["file_id"]

    # 2. Confirm Mapping
    mapping_payload = {
        "dataset_name": "E2E Test Dataset",
        "files": [
            {
                "file_id": bank_file_id,
                "filename": "bank_transactions.csv",
                "file_type": "csv",
                "data_type": "BANK",
                "mapping": {
                    "bank_txn_id": "bank_txn_id",
                    "transaction_date": "transaction_date",
                    "amount": "amount"
                }
            },
            {
                "file_id": gw_file_id,
                "filename": "gateway_transactions.csv",
                "file_type": "csv",
                "data_type": "GATEWAY",
                "mapping": {
                    "gateway_txn_id": "gateway_txn_id",
                    "transaction_date": "transaction_date",
                    "amount": "amount"
                }
            },
            {
                "file_id": inv_file_id,
                "filename": "invoices.csv",
                "file_type": "csv",
                "data_type": "INVOICE",
                "mapping": {
                    "invoice_id": "invoice_id",
                    "invoice_date": "invoice_date",
                    "amount": "amount"
                }
            }
        ]
    }
    
    res_confirm = client.post("/api/upload/confirm", json=mapping_payload)
    assert res_confirm.status_code == 200, res_confirm.text
    dataset_id = res_confirm.json()["dataset_id"]
    
    # 3. Verify DB Counts with fresh session
    db.close()
    db = TestingSessionLocal()
    b_count = db.query(BankTransaction).filter_by(dataset_id=dataset_id).count()
    g_count = db.query(GatewayTransaction).filter_by(dataset_id=dataset_id).count()
    i_count = db.query(Invoice).filter_by(dataset_id=dataset_id).count()
    
    assert b_count > 0
    assert g_count > 0
    assert i_count > 0
    
    bank_sample = db.query(BankTransaction).filter_by(dataset_id=dataset_id).first()
    assert bank_sample.bank_txn_id.startswith(dataset_id[:8])

    # 4. Run Reconciliation
    res_recon = client.post("/api/reconciliation/run", json={"use_ai": False, "dataset_id": dataset_id})
    assert res_recon.status_code == 200, res_recon.text
    run_data = res_recon.json()
    assert run_data["dataset_id"] == dataset_id
    
    # 5. Verify Metrics API
    res_metrics = client.get(f"/api/metrics?dataset_id={dataset_id}")
    assert res_metrics.status_code == 200
    metrics = res_metrics.json()
    assert metrics["total_source_records"] > 0
    assert metrics["review_count"] >= 0
