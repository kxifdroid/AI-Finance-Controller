import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from app.db.base import Base
from app.models.audit import AuditLog
from app.services.audit import AuditService


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_audit.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_audit_log_entry_creation(test_db):
    entry = AuditService.log(
        db=test_db,
        entity_type="match",
        entity_id="M_TEST_1001",
        action="auto_matched",
        rule_or_reason="exact_amount_date_ref",
        actor="system",
        after_status="match",
    )
    test_db.commit()

    assert entry.log_id.startswith("LOG_")
    assert entry.entity_type == "match"
    assert entry.entity_id == "M_TEST_1001"
    assert entry.action == "auto_matched"
    assert entry.rule_or_reason == "exact_amount_date_ref"
    assert entry.after_status == "match"

    # Query from DB
    saved = test_db.query(AuditLog).filter_by(entity_id="M_TEST_1001").first()
    assert saved is not None
    assert saved.action == "auto_matched"
