"""
End-to-end integration tests for all FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.base import Base
from app.db.session import get_db

# Create isolated test database
test_engine = create_engine("sqlite:///./test_api.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    try:
        if os.path.exists("./test_api.db"):
            os.remove("./test_api.db")
    except Exception:
        pass


client = TestClient(app)


def test_health_and_root():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "operational"


def test_generate_data_and_run_reconciliation():
    # 1. Generate synthetic data
    res_gen = client.post("/api/data/generate?count=50")
    assert res_gen.status_code == 200
    assert res_gen.json()["status"] == "success"

    # 2. Run reconciliation pipeline
    res_run = client.post("/api/reconciliation/run", json={"use_ai": True})
    assert res_run.status_code == 200
    data = res_run.json()
    assert data["status"] == "COMPLETED"
    assert data["total_records"] > 0
    assert data["matched_count"] > 0

    run_id = data["run_id"]

    # 3. Check latest run
    res_latest = client.get("/api/reconciliation/latest")
    assert res_latest.status_code == 200
    assert res_latest.json()["run_id"] == run_id

    # 4. List transactions
    res_tx = client.get("/api/transactions")
    assert res_tx.status_code == 200
    assert len(res_tx.json()["items"]) > 0

    # 5. Get transaction detail
    first_tx_id = res_tx.json()["items"][0]["match_id"]
    res_detail = client.get(f"/api/transactions/{first_tx_id}")
    assert res_detail.status_code == 200
    assert "features" in res_detail.json()

    # 6. List and update exceptions
    res_exc = client.get("/api/exceptions")
    assert res_exc.status_code == 200
    if len(res_exc.json()["items"]) > 0:
        exc_id = res_exc.json()["items"][0]["exception_id"]
        res_patch = client.patch(f"/api/exceptions/{exc_id}", json={"status": "IN_REVIEW", "notes": "Auditing discrepancy"})
        assert res_patch.status_code == 200
        assert res_patch.json()["status"] == "IN_REVIEW"

    # 7. Get metrics summary
    res_metrics = client.get("/api/metrics")
    assert res_metrics.status_code == 200
    assert res_metrics.json()["has_run"] is True
    assert "status_distribution" in res_metrics.json()

    # 8. Finance Q&A Chat
    res_chat = client.post("/api/finance/chat", json={"message": "What is our reconciliation status and match rate?"})
    assert res_chat.status_code == 200
    assert "answer" in res_chat.json()
    assert len(res_chat.json()["tools_used"]) > 0

    # 9. Cash Forecast
    res_forecast = client.get("/api/forecast")
    assert res_forecast.status_code == 200
    assert len(res_forecast.json()["forecast_points"]) == 4
