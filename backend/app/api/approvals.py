"""
API Endpoints for Human Approval Workflow.

These endpoints provide the human-in-the-loop approval mechanism for
sensitive financial actions. All actions that modify financial records
or reconciliation state must go through this approval flow.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.services.approval import ApprovalService, ApprovalRequest, ApprovalStatus, ApprovalActionType
from app.services.audit import AuditService

router = APIRouter(prefix="/approvals", tags=["Approvals"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ApprovalRequestResponse(BaseModel):
    id: str
    action_type: str
    entity_type: str
    entity_id: str
    requested_by: str
    status: str
    proposal_summary: str
    proposal_details: Optional[dict] = None
    investigation_id: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_recommendation: Optional[str] = None
    evidence_json: Optional[dict] = None
    amount_involved: float
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: str
    executed_at: Optional[str] = None
    
    model_config = {"from_attributes": True}


class CreateApprovalRequest(BaseModel):
    action_type: str  # MARK_RECONCILED, VOID_DUPLICATE, etc.
    entity_type: str  # exception, match, transaction
    entity_id: str
    proposal_summary: str
    proposal_details: Optional[dict] = None
    evidence: Optional[dict] = None
    amount_involved: float = 0.0
    ai_confidence: Optional[float] = None
    ai_recommendation: Optional[str] = None
    investigation_id: Optional[str] = None
    run_id: Optional[str] = None


class ApproveRequest(BaseModel):
    reviewed_by: str
    review_notes: Optional[str] = None
    execute_action: bool = True


class RejectRequest(BaseModel):
    reviewed_by: str
    rejection_reason: str
    review_notes: Optional[str] = None


class ApprovalListResponse(BaseModel):
    items: List[ApprovalRequestResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=ApprovalListResponse)
def list_pending_approvals(
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    status: Optional[str] = Query("PENDING", description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    List approval requests with optional filters.
    Default shows pending approvals that require human review.
    """
    offset = (page - 1) * page_size
    
    query = db.query(ApprovalRequest)
    
    if status:
        query = query.filter(ApprovalRequest.status == status.upper())
    if action_type:
        try:
            at = ApprovalActionType[action_type.upper()]
            query = query.filter(ApprovalRequest.action_type == at)
        except KeyError:
            pass
    if entity_type:
        query = query.filter(ApprovalRequest.entity_type == entity_type)
    
    total = query.count()
    items = query.order_by(ApprovalRequest.created_at.desc()).offset(offset).limit(page_size).all()
    
    return ApprovalListResponse(
        items=[_format_approval(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{approval_id}", response_model=ApprovalRequestResponse)
def get_approval(
    approval_id: str,
    db: Session = Depends(get_db),
):
    """
    Get details of a specific approval request.
    """
    approval = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval request {approval_id} not found")
    
    return _format_approval(approval)


@router.post("", response_model=ApprovalRequestResponse)
def create_approval(
    req: CreateApprovalRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new approval request for a sensitive action.
    
    This is typically called by the AI agent when it wants to propose
    an action that requires human authorization.
    """
    try:
        action_type = ApprovalActionType[req.action_type.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid action_type. Valid types: {[t.value for t in ApprovalActionType]}"
        )
    
    approval = ApprovalService.create_approval_request(
        db=db,
        action_type=action_type,
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        proposal_summary=req.proposal_summary,
        proposal_details=req.proposal_details,
        evidence=req.evidence,
        amount_involved=req.amount_involved,
        ai_confidence=req.ai_confidence,
        ai_recommendation=req.ai_recommendation,
        investigation_id=req.investigation_id,
        run_id=req.run_id,
    )
    
    return _format_approval(approval)


@router.post("/{approval_id}/approve", response_model=ApprovalRequestResponse)
def approve_request(
    approval_id: str,
    req: ApproveRequest,
    db: Session = Depends(get_db),
):
    """
    Approve a pending approval request.
    
    If execute_action is True (default), the approved action will be
    immediately executed after approval.
    """
    try:
        approval = ApprovalService.approve(
            db=db,
            approval_id=approval_id,
            reviewed_by=req.reviewed_by,
            review_notes=req.review_notes,
            execute_action=req.execute_action,
        )
        return _format_approval(approval)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{approval_id}/reject", response_model=ApprovalRequestResponse)
def reject_request(
    approval_id: str,
    req: RejectRequest,
    db: Session = Depends(get_db),
):
    """
    Reject a pending approval request.
    
    A rejection_reason is required to document why the action was denied.
    """
    try:
        approval = ApprovalService.reject(
            db=db,
            approval_id=approval_id,
            reviewed_by=req.reviewed_by,
            rejection_reason=req.rejection_reason,
            review_notes=req.review_notes,
        )
        return _format_approval(approval)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history/{entity_id}")
def get_approval_history(
    entity_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Get approval history for a specific entity.
    """
    history = ApprovalService.get_approval_history(
        db=db,
        entity_id=entity_id,
        limit=limit,
    )
    
    return {
        "entity_id": entity_id,
        "approvals": [_format_approval(a) for a in history],
    }


def _format_approval(approval: ApprovalRequest) -> ApprovalRequestResponse:
    """Format approval request for API response."""
    return ApprovalRequestResponse(
        id=approval.id,
        action_type=approval.action_type.value if approval.action_type else "",
        entity_type=approval.entity_type,
        entity_id=approval.entity_id,
        requested_by=approval.requested_by,
        status=approval.status.value if approval.status else "PENDING",
        proposal_summary=approval.proposal_summary,
        proposal_details=approval.proposal_details,
        investigation_id=approval.investigation_id,
        ai_confidence=approval.ai_confidence,
        ai_recommendation=approval.ai_recommendation,
        evidence_json=approval.evidence_json,
        amount_involved=approval.amount_involved or 0.0,
        reviewed_by=approval.reviewed_by,
        reviewed_at=str(approval.reviewed_at) if approval.reviewed_at else None,
        review_notes=approval.review_notes,
        rejection_reason=approval.rejection_reason,
        created_at=str(approval.created_at),
        executed_at=str(approval.executed_at) if approval.executed_at else None,
    )
