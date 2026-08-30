import os
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db, Base, engine
from app.models.dataset import Dataset, FileRecord
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
import pandas as pd

# Override DB dependency
def override_get_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    test_engine = create_engine("sqlite:///./test_upload.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(scope="function", autouse=True)
def setup_db():
    from sqlalchemy import create_engine
    test_engine = create_engine("sqlite:///./test_upload.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    try:
        if os.path.exists("./test_upload.db"):
            os.remove("./test_upload.db")
    except Exception:
        pass

@pytest.fixture
def test_files():
    # Create test CSV files
    os.makedirs("data/test", exist_ok=True)
    
    bank_df = pd.DataFrame({
        "bank_transaction_id": ["B1", "B2"],
        "transaction_date": ["2026-07-01", "2026-07-02"],
        "credit_amount": [100.0, 200.0]
    })
    bank_df.to_csv("data/test/test_bank.csv", index=False)
    
    gw_df = pd.DataFrame({
        "gw_id": ["G1", "G2"],
        "date": ["2026-07-01", "2026-07-02"],
        "money": [100.0, 200.0]
    })
    gw_df.to_csv("data/test/test_gw.csv", index=False)
    
    inv_df = pd.DataFrame({
        "inv_no": ["INV1"],
        "date": ["2026-07-01"],
        "total": [100.0]
    })
    inv_df.to_csv("data/test/test_inv.csv", index=False)
    
    yield {
        "bank": "data/test/test_bank.csv",
        "gateway": "data/test/test_gw.csv",
        "invoice": "data/test/test_inv.csv"
    }
    
    # Cleanup
    for f in ["test_bank.csv", "test_gw.csv", "test_inv.csv"]:
        if os.path.exists(f"data/test/{f}"):
            os.remove(f"data/test/{f}")

def test_1_bank_mapping(setup_db, test_files):
    # Upload file
    with open(test_files["bank"], "rb") as f:
        res = client.post("/api/upload/file", files={"file": ("test_bank.csv", f, "text/csv")})
    assert res.status_code == 200
    file_id = res.json()["file_id"]

    # Confirm mapping
    payload = {
        "dataset_name": "Test 1",
        "files": [{
            "file_id": file_id,
            "filename": "test_bank.csv",
            "file_type": "csv",
            "data_type": "BANK",
            "mapping": {
                "bank_txn_id": "bank_transaction_id",
                "transaction_date": "transaction_date",
                "amount": "credit_amount"
            }
        }]
    }
    res = client.post("/api/upload/confirm", json=payload)
    assert res.status_code == 200
    assert res.json()["success"] == True
    assert res.json()["files"][0]["rows_ingested"] == 2

def test_2_custom_column_names(setup_db, test_files):
    # Gateway with totally custom names
    with open(test_files["gateway"], "rb") as f:
        res = client.post("/api/upload/file", files={"file": ("test_gw.csv", f, "text/csv")})
    file_id = res.json()["file_id"]

    payload = {
        "dataset_name": "Test 2",
        "files": [{
            "file_id": file_id,
            "filename": "test_gw.csv",
            "file_type": "csv",
            "data_type": "GATEWAY",
            "mapping": {
                "gateway_txn_id": "gw_id",
                "transaction_date": "date",
                "amount": "money"
            }
        }]
    }
    res = client.post("/api/upload/confirm", json=payload)
    assert res.status_code == 200
    assert res.json()["success"] == True

def test_3_missing_required_mapping(setup_db, test_files):
    with open(test_files["invoice"], "rb") as f:
        res = client.post("/api/upload/file", files={"file": ("test_inv.csv", f, "text/csv")})
    file_id = res.json()["file_id"]

    payload = {
        "dataset_name": "Test 3",
        "files": [{
            "file_id": file_id,
            "filename": "test_inv.csv",
            "file_type": "csv",
            "data_type": "INVOICE",
            "mapping": {
                "invoice_id": "inv_no",
                "invoice_date": "date"
                # Missing amount
            }
        }]
    }
    res = client.post("/api/upload/confirm", json=payload)
    assert res.status_code == 400
    assert "Missing required mapping for canonical field" in res.json()["detail"]

def test_4_invalid_column(setup_db, test_files):
    with open(test_files["invoice"], "rb") as f:
        res = client.post("/api/upload/file", files={"file": ("test_inv.csv", f, "text/csv")})
    file_id = res.json()["file_id"]

    payload = {
        "dataset_name": "Test 4",
        "files": [{
            "file_id": file_id,
            "filename": "test_inv.csv",
            "file_type": "csv",
            "data_type": "INVOICE",
            "mapping": {
                "invoice_id": "inv_no",
                "invoice_date": "date",
                "amount": "non_existent_column"
            }
        }]
    }
    res = client.post("/api/upload/confirm", json=payload)
    assert res.status_code == 400

def test_5_multi_file_upload(setup_db, test_files):
    f1 = client.post("/api/upload/file", files={"file": open(test_files["bank"], "rb")}).json()
    f2 = client.post("/api/upload/file", files={"file": open(test_files["gateway"], "rb")}).json()

    payload = {
        "dataset_name": "Multi Upload",
        "files": [
            {
                "file_id": f1["file_id"],
                "filename": "test_bank.csv",
                "file_type": "csv",
                "data_type": "BANK",
                "mapping": {"bank_txn_id": "bank_transaction_id", "transaction_date": "transaction_date", "amount": "credit_amount"}
            },
            {
                "file_id": f2["file_id"],
                "filename": "test_gw.csv",
                "file_type": "csv",
                "data_type": "GATEWAY",
                "mapping": {"gateway_txn_id": "gw_id", "transaction_date": "date", "amount": "money"}
            }
        ]
    }
    res = client.post("/api/upload/confirm", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] == True
    assert len(data["files"]) == 2

def test_6_dataset_isolation(setup_db, test_files):
    # A single run should only reconcile records with the provided dataset_id
    f1 = client.post("/api/upload/file", files={"file": open(test_files["bank"], "rb")}).json()
    payload = {
        "dataset_name": "Isolation",
        "files": [{
            "file_id": f1["file_id"],
            "filename": "test_bank.csv",
            "file_type": "csv",
            "data_type": "BANK",
            "mapping": {"bank_txn_id": "bank_transaction_id", "transaction_date": "transaction_date", "amount": "credit_amount"}
        }]
    }
    ds_res = client.post("/api/upload/confirm", json=payload)
    dataset_id = ds_res.json()["dataset_id"]

    res = client.post("/api/reconciliation/run", json={"use_ai": False, "dataset_id": dataset_id})
    assert res.status_code == 200
    run_data = res.json()
    assert run_data["total_records"] == 2 # Only the 2 bank records from this dataset

def test_7_end_to_end(setup_db, test_files):
    f_inv = client.post("/api/upload/file", files={"file": open(test_files["invoice"], "rb")}).json()
    payload = {
        "dataset_name": "E2E",
        "files": [{
            "file_id": f_inv["file_id"],
            "filename": "test_inv.csv",
            "file_type": "csv",
            "data_type": "INVOICE",
            "mapping": {"invoice_id": "inv_no", "invoice_date": "date", "amount": "total"}
        }]
    }
    ds_res = client.post("/api/upload/confirm", json=payload)
    dataset_id = ds_res.json()["dataset_id"]

    recon_res = client.post("/api/reconciliation/run", json={"use_ai": False, "dataset_id": dataset_id})
    assert recon_res.status_code == 200

    metrics_res = client.get(f"/api/metrics?dataset_id={dataset_id}")
    assert metrics_res.status_code == 200
    assert metrics_res.json()["total_records"] == 1

def test_8_retry(setup_db, test_files):
    # Uploading the same file twice in different datasets should not crash, but they are isolated datasets
    f1 = client.post("/api/upload/file", files={"file": open(test_files["bank"], "rb")}).json()
    payload = {
        "dataset_name": "Retry",
        "files": [{
            "file_id": f1["file_id"],
            "filename": "test_bank.csv",
            "file_type": "csv",
            "data_type": "BANK",
            "mapping": {"bank_txn_id": "bank_transaction_id", "transaction_date": "transaction_date", "amount": "credit_amount"}
        }]
    }
    res1 = client.post("/api/upload/confirm", json=payload)
    assert res1.status_code == 200
    
    # Normally duplicate keys (like bank_txn_id) are merged/upserted by the IngestionService via db.merge
    # The existing ingestion service uses db.merge, which updates existing records if they have the same primary key.
    # Wait, the DB model uses a composite key or just an id?
    # BankTransaction has `id` (uuid primary key), and `bank_txn_id` which might be unique.
    # Actually `db.merge` on a model without ID set will just insert. 
    # Let's just ensure the second upload doesn't throw a 500.
    
    # We must re-upload the file since it's deleted after confirm
    f2 = client.post("/api/upload/file", files={"file": open(test_files["bank"], "rb")}).json()
    payload["files"][0]["file_id"] = f2["file_id"]
    res2 = client.post("/api/upload/confirm", json=payload)
    assert res2.status_code == 200
