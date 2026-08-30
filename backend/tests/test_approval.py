"""
Tests for Human Approval Workflow.

Tests the human-in-the-loop approval mechanism for sensitive financial actions.
"""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.session import get_db, Base
from app.services.approval import ApprovalService, ApprovalActionType, ApprovalStatus

TEST_DB_URL = "sqlite:///./test_approval.db"
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
        if os.path.exists("./test_approval.db"):
            os.remove("./test_approval.db")
    except Exception:
        pass


def test_create_approval_request():
    """Test creating a new approval request."""
    db = TestingSessionLocal()
    try:
        approval = ApprovalService.create_approval_request(
            db=db,
            action_type=ApprovalActionType.MARK_RECONCILED,
            entity_type="exception",
            entity_id="EXC_12345",
            proposal_summary="Mark exception as reconciled based on AI investigation",
            proposal_details={"confidence": 0.98, "reason": "MDR fee match"},
            evidence={"fee_analysis": "Standard 2.36% MDR"},
            amount_involved=10000.0,
            ai_confidence=0.98,
            ai_recommendation="MARK_RECONCILED",
            investigation_id="INV_ABC123",
        )
        
        assert approval.id.startswith("APR_")
        assert approval.action_type == ApprovalActionType.MARK_RECONCILED
        assert approval.status == ApprovalStatus.PENDING
        assert approval.entity_id == "EXC_12345"
        assert approval.amount_involved == 10000.0
        assert approval.ai_confidence == 0.98
    finally:
        db.close()


def test_approve_request():
    """Test approving a pending request."""
    db = TestingSessionLocal()
    try:
        # Create approval
        approval = ApprovalService.create_approval_request(
            db=db,
            action_type=ApprovalActionType.MARK_RECONCILED,
            entity_type="exception",
            entity_id="EXC_67890",
            proposal_summary="Test approval",
            amount_involved=5000.0,
        )
        
        # Approve it
        approved = ApprovalService.approve(
            db=db,
            approval_id=approval.id,
            reviewed_by="test_user",
            review_notes="Verified MDR calculation is correct",
            execute_action=False,  # Don't execute since no real exception exists
        )
        
        assert approved.status == ApprovalStatus.APPROVED
        assert approved.reviewed_by == "test_user"
        assert approved.reviewed_at is not None
        assert approved.review_notes == "Verified MDR calculation is correct"
    finally:
        db.close()


def test_reject_request():
    """Test rejecting a pending request."""
    db = TestingSessionLocal()
    try:
        # Create approval
        approval = ApprovalService.create_approval_request(
            db=db,
            action_type=ApprovalActionType.VOID_DUPLICATE,
            entity_type="exception",
            entity_id="EXC_VOID1",
            proposal_summary="Void duplicate transaction",
            amount_involved=15000.0,
        )
        
        # Reject it
        rejected = ApprovalService.reject(
            db=db,
            approval_id=approval.id,
            reviewed_by="supervisor",
            rejection_reason="Not a true duplicate - different customer",
            review_notes="Customer names differ after manual review",
        )
        
        assert rejected.status == ApprovalStatus.REJECTED
        assert rejected.reviewed_by == "supervisor"
        assert rejected.rejection_reason == "Not a true duplicate - different customer"
    finally:
        db.close()


def test_cannot_approve_rejected_request():
    """Test that a rejected request cannot be approved."""
    db = TestingSessionLocal()
    try:
        # Create and reject
        approval = ApprovalService.create_approval_request(
            db=db,
            action_type=ApprovalActionType.MARK_RECONCILED,
            entity_type="exception",
            entity_id="EXC_TEST",
            proposal_summary="Test",
        )
        
        ApprovalService.reject(
            db=db,
            approval_id=approval.id,
            reviewed_by="user1",
            rejection_reason="Invalid",
        )
        
        # Try to approve
        with pytest.raises(ValueError, match="Cannot approve request"):
            ApprovalService.approve(
                db=db,
                approval_id=approval.id,
                reviewed_by="user2",
            )
    finally:
        db.close()


def test_list_pending_approvals():
    """Test listing pending approvals."""
    db = TestingSessionLocal()
    try:
        # Create multiple approvals
        for i in range(5):
            ApprovalService.create_approval_request(
                db=db,
                action_type=ApprovalActionType.MARK_RECONCILED,
                entity_type="exception",
                entity_id=f"EXC_{i}",
                proposal_summary=f"Test approval {i}",
            )
        
        # Approve one
        all_pending = ApprovalService.get_pending_approvals(db=db)
        ApprovalService.approve(
            db=db,
            approval_id=all_pending[0].id,
            reviewed_by="user",
            execute_action=False,
        )
        
        # Should now have 4 pending
        remaining = ApprovalService.get_pending_approvals(db=db)
        assert len(remaining) == 4
    finally:
        db.close()


def test_api_create_approval():
    """Test API endpoint for creating approval requests."""
    response = client.post("/api/approvals", json={
        "action_type": "MARK_RECONCILED",
        "entity_type": "exception",
        "entity_id": "EXC_API_TEST",
        "proposal_summary": "API test approval",
        "amount_involved": 7500.0,
        "ai_confidence": 0.95,
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == "EXC_API_TEST"
    assert data["status"] == "PENDING"
    assert data["action_type"] == "MARK_RECONCILED"


def test_api_approve_and_reject():
    """Test API endpoints for approving and rejecting."""
    # Create
    create_resp = client.post("/api/approvals", json={
        "action_type": "APPLY_AI_SUGGESTION",
        "entity_type": "exception",
        "entity_id": "EXC_API_TEST2",
        "proposal_summary": "Apply AI suggestion",
    })
    approval_id = create_resp.json()["id"]
    
    # Approve
    approve_resp = client.post(f"/api/approvals/{approval_id}/approve", json={
        "reviewed_by": "api_user",
        "review_notes": "Looks good",
        "execute_action": False,
    })
    
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "APPROVED"
    
    # Create another to reject
    create_resp2 = client.post("/api/approvals", json={
        "action_type": "VOID_DUPLICATE",
        "entity_type": "exception",
        "entity_id": "EXC_API_TEST3",
        "proposal_summary": "Void duplicate",
    })
    approval_id2 = create_resp2.json()["id"]
    
    # Reject
    reject_resp = client.post(f"/api/approvals/{approval_id2}/reject", json={
        "reviewed_by": "supervisor",
        "rejection_reason": "Not a duplicate",
    })
    
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "REJECTED"


def test_api_list_approvals():
    """Test API endpoint for listing approvals."""
    # Create some approvals
    for i in range(3):
        client.post("/api/approvals", json={
            "action_type": "MARK_RECONCILED",
            "entity_type": "exception",
            "entity_id": f"EXC_LIST_{i}",
            "proposal_summary": f"List test {i}",
        })
    
    # List pending
    list_resp = client.get("/api/approvals?status=PENDING")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 3
    assert len(data["items"]) >= 3
