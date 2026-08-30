"""
Reconciliation Pipeline Execution API Routes.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.reconciliation import ReconciliationRun
from app.schemas.reconciliation import (
    RunReconciliationRequest,
    ReconciliationRunResponse,
)
from app.services.reconciliation import ReconciliationService

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


@router.post("/run", response_model=ReconciliationRunResponse)
async def run_pipeline(
    payload: Optional[RunReconciliationRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Executes the multi-source reconciliation pipeline with candidate generation,
    deterministic scoring, AI verification, and ground-truth evaluation.
    """
    use_ai = payload.use_ai if payload else True
    dataset_id = payload.dataset_id if payload else None
    service = ReconciliationService()
    try:
        run_record = await service.run_reconciliation(db=db, use_ai=use_ai, dataset_id=dataset_id)
        return run_record
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reconciliation run failed: {str(e)}")


@router.get("/latest", response_model=Optional[ReconciliationRunResponse])
def get_latest_run(db: Session = Depends(get_db)):
    """Fetches the most recent reconciliation run metadata."""
    run = db.query(ReconciliationRun).order_by(desc(ReconciliationRun.started_at)).first()
    return run


@router.get("/{run_id}", response_model=ReconciliationRunResponse)
def get_run_by_id(run_id: str, db: Session = Depends(get_db)):
    """Fetches a reconciliation run by ID."""
    run = db.query(ReconciliationRun).filter(ReconciliationRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Reconciliation run not found")
    return run


@router.post("/reset")
def reset_reconciliation(
    payload: Optional[dict] = None,
    db: Session = Depends(get_db)
):
    """
    Cancels and clears reconciliation runs, matches, exceptions, uploaded transactions, datasets, and audit logs.
    Guarantees a 100% clean slate when resetting.
    """
    try:
        from app.models.reconciliation import Match, ReconciliationRun
        from app.models.exception import ExceptionRecord
        from app.models.evaluation import EvaluationResult
        from app.models.audit import AuditLog
        from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
        from app.models.dataset import Dataset, FileRecord
        from app.models.forecast import CashFlow

        dataset_id = payload.get("dataset_id") if payload else None
        clear_all_data = payload.get("clear_all_data", True) if payload else True

        if dataset_id and not clear_all_data:
            # Targeted reset for a specific dataset run
            run_ids = [r.run_id for r in db.query(ReconciliationRun).filter(ReconciliationRun.dataset_id == dataset_id).all()]
            if run_ids:
                db.query(Match).filter(Match.run_id.in_(run_ids)).delete(synchronize_session=False)
                db.query(ExceptionRecord).filter(ExceptionRecord.run_id.in_(run_ids)).delete(synchronize_session=False)
                db.query(EvaluationResult).filter(EvaluationResult.run_id.in_(run_ids)).delete(synchronize_session=False)
            db.query(ReconciliationRun).filter(ReconciliationRun.dataset_id == dataset_id).delete(synchronize_session=False)
        else:
            # Complete reset: clear all matches, exceptions, evaluations, runs, and transactions
            db.query(Match).delete(synchronize_session=False)
            db.query(ExceptionRecord).delete(synchronize_session=False)
            db.query(EvaluationResult).delete(synchronize_session=False)
            db.query(ReconciliationRun).delete(synchronize_session=False)
            db.query(BankTransaction).delete(synchronize_session=False)
            db.query(GatewayTransaction).delete(synchronize_session=False)
            db.query(Invoice).delete(synchronize_session=False)
            db.query(FileRecord).delete(synchronize_session=False)
            db.query(Dataset).delete(synchronize_session=False)
            db.query(CashFlow).delete(synchronize_session=False)
            db.query(AuditLog).delete(synchronize_session=False)

            try:
                from app.services.approval import ApprovalRequest
                db.query(ApprovalRequest).delete(synchronize_session=False)
            except Exception:
                pass

        db.commit()
        return {"status": "success", "message": "All previous data, uploaded transactions, and reconciliation analyses have been completely cleared."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reset analysis: {str(e)}")
