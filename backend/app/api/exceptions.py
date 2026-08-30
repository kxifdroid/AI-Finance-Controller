"""
Exception Triage and Lifecycle Management API Routes.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.exception import ExceptionRecord
from datetime import datetime
import uuid

from app.schemas.exception import (
    ExceptionResponse,
    ExceptionListResponse,
    UpdateExceptionStatusRequest,
    ApproveExceptionRequest,
    RejectExceptionRequest,
    AIInvestigationResponse,
)
from app.services.exceptions import ExceptionService
from app.agents.investigator import ExceptionInvestigatorAgent


router = APIRouter(prefix="/exceptions", tags=["Exceptions"])


@router.get("", response_model=ExceptionListResponse)
def list_exceptions(
    status: Optional[str] = Query(None, description="OPEN, IN_REVIEW, RESOLVED, IGNORED"),
    severity: Optional[str] = Query(None, description="HIGH, MEDIUM, LOW"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Returns paginated exception records for the audit and triage dashboard.
    """
    query = db.query(ExceptionRecord)
    if status:
        query = query.filter(ExceptionRecord.status == status.upper())
    if severity:
        query = query.filter(ExceptionRecord.severity == severity.upper())

    total = query.count()
    offset = (page - 1) * page_size
    records = query.order_by(desc(ExceptionRecord.created_at)).offset(offset).limit(page_size).all()

    items = [ExceptionResponse.model_validate(r) for r in records]

    return ExceptionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 1,
        items=items,
    )


@router.get("/{id}", response_model=ExceptionResponse)
def get_exception_by_id(id: str, db: Session = Depends(get_db)):
    """Fetches a specific exception by its exception_id."""
    record = db.query(ExceptionRecord).filter(ExceptionRecord.exception_id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Exception not found")
    return record


@router.patch("/{id}", response_model=ExceptionResponse)
def update_exception_status(
    id: str,
    payload: UpdateExceptionStatusRequest,
    db: Session = Depends(get_db),
):
    """
    Updates the lifecycle status (OPEN -> IN_REVIEW -> RESOLVED -> IGNORED) and resolution notes.
    """
    record = ExceptionService.update_exception_status(
        db=db,
        exception_id=id,
        status=payload.status,
        notes=payload.notes,
        resolved_by=payload.resolved_by or "Operator",
    )
    if not record:
        raise HTTPException(status_code=404, detail="Exception record not found")
    return record

@router.post("/{id}/investigate", response_model=AIInvestigationResponse)
def investigate_exception(
    id: str,
    use_ai: bool = Query(False, description="Whether to invoke LLM semantic reasoning"),
    db: Session = Depends(get_db),
):
    """
    Runs autonomous AI investigation on the specified exception record,
    decomposing mathematical settlement variance, cross-referencing merchant policies,
    and returning structured evidence.
    """
    record = db.query(ExceptionRecord).filter(ExceptionRecord.exception_id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Exception record not found")

    agent = ExceptionInvestigatorAgent()
    investigation_dict = agent.investigate(db=db, exception_record=record, use_ai=use_ai)
    return AIInvestigationResponse.model_validate(investigation_dict)



@router.post("/{id}/approve", response_model=ExceptionResponse)
def approve_exception(
    id: str,
    payload: ApproveExceptionRequest,
    db: Session = Depends(get_db),
):
    """
    1-Click AI / Human Approval for an exception record.
    Marks exception as RESOLVED with audit notes.
    """
    record = db.query(ExceptionRecord).filter(ExceptionRecord.exception_id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Exception record not found")

    approval_note = payload.notes or "Approved resolution via AI Investigation verification."
    record.status = "RESOLVED"
    record.notes = f"[APPROVED] {approval_note}" if not record.notes else f"{record.notes} | [APPROVED] {approval_note}"
    record.resolved_by = "AI Controller / Finance Operator"
    record.updated_at = datetime.now()

    db.commit()
    db.refresh(record)
    return record


@router.post("/{id}/reject", response_model=ExceptionResponse)
def reject_exception(
    id: str,
    payload: RejectExceptionRequest,
    db: Session = Depends(get_db),
):
    """
    Rejects auto-resolution and escalates exception for senior supervisor review.
    """
    record = db.query(ExceptionRecord).filter(ExceptionRecord.exception_id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Exception record not found")

    rejection_note = payload.reason or "Rejected auto-resolution. Escalated for manual audit."
    record.status = "IN_REVIEW"
    record.severity = "HIGH"
    record.notes = f"[REJECTED & ESCALATED] {rejection_note}" if not record.notes else f"{record.notes} | [REJECTED & ESCALATED] {rejection_note}"
    record.resolved_by = "Supervisor Escalation"
    record.updated_at = datetime.now()

    db.commit()
    db.refresh(record)
    return record

