"""
Metrics, KPIs, and Evaluation Analytics API Routes.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.db.session import get_db
from app.models.reconciliation import ReconciliationRun, Match
from app.models.exception import ExceptionRecord
from app.models.evaluation import EvaluationResult

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("")
def get_metrics_summary(dataset_id: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Returns aggregated KPI metrics, operational performance, and evaluation benchmarks.
    """
    q = db.query(ReconciliationRun)
    if dataset_id:
        q = q.filter(ReconciliationRun.dataset_id == dataset_id)
    latest_run = q.order_by(desc(ReconciliationRun.started_at)).first()
    
    if not latest_run:
        return {
            "has_run": False,
            "message": "No reconciliation run has been executed yet.",
        }

    total = latest_run.total_records or 1
    match_rate = round((latest_run.matched_count / total) * 100, 2)
    exception_rate = round((latest_run.exception_count / total) * 100, 2)
    review_rate = round((latest_run.review_count / total) * 100, 2)
    ai_escalation_rate = round((latest_run.ai_escalation_count / total) * 100, 2)

    # Compute actual source record count
    from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
    b_count = db.query(BankTransaction).filter(BankTransaction.dataset_id == latest_run.dataset_id).count() if latest_run.dataset_id else 0
    g_count = db.query(GatewayTransaction).filter(GatewayTransaction.dataset_id == latest_run.dataset_id).count() if latest_run.dataset_id else 0
    i_count = db.query(Invoice).filter(Invoice.dataset_id == latest_run.dataset_id).count() if latest_run.dataset_id else 0
    total_source_records = b_count + g_count + i_count
    
    # Financial total volume
    total_volume = latest_run.total_matched_volume + latest_run.total_review_volume + latest_run.total_exception_volume
    
    # AI Stats
    ai_verified_count = db.query(Match).filter(Match.run_id == latest_run.run_id, Match.ai_verification_status == "VERIFIED").count()
    ai_failed_count = db.query(Match).filter(Match.run_id == latest_run.run_id, Match.ai_verification_status.in_(["REVIEW_FALLBACK", "CIRCUIT_OPEN"])).count()

    # Status distribution for charts
    status_distribution = [
        {"name": "Auto Matched", "value": latest_run.matched_count, "color": "#10B981"},
        {"name": "Human Review", "value": latest_run.review_count, "color": "#F59E0B"},
        {"name": "Exceptions", "value": latest_run.exception_count, "color": "#EF4444"},
        {"name": "Duplicates", "value": latest_run.duplicate_count, "color": "#8B5CF6"},
        {"name": "Missing", "value": latest_run.missing_count, "color": "#6B7280"},
    ]

    # Exceptions grouped by type
    exc_by_type_rows = db.query(
        ExceptionRecord.exception_type,
        func.count(ExceptionRecord.exception_id).label("count"),
        func.sum(ExceptionRecord.amount_involved).label("total_amount"),
    ).filter(ExceptionRecord.run_id == latest_run.run_id)\
     .group_by(ExceptionRecord.exception_type).all()

    exceptions_by_type = [
        {"type": r[0], "count": r[1], "amount": round(r[2] or 0.0, 2)}
        for r in exc_by_type_rows
    ]

    # Exceptions grouped by severity
    exc_by_sev_rows = db.query(
        ExceptionRecord.severity,
        func.count(ExceptionRecord.exception_id).label("count"),
    ).filter(ExceptionRecord.run_id == latest_run.run_id)\
     .group_by(ExceptionRecord.severity).all()

    severity_distribution = [
        {"severity": r[0], "count": r[1]}
        for r in exc_by_sev_rows
    ]

    # Latest Evaluation Results from Ground Truth
    eval_record = db.query(EvaluationResult).filter(EvaluationResult.run_id == latest_run.run_id).first()

    return {
        "has_run": True,
        "run_id": latest_run.run_id,
        "started_at": latest_run.started_at,
        "completed_at": latest_run.completed_at,
        "total_records": latest_run.total_records, # Triplets
        "total_source_records": total_source_records, # Source rows
        "matched_count": latest_run.matched_count,
        "review_count": latest_run.review_count,
        "exception_count": latest_run.exception_count,
        "duplicate_count": latest_run.duplicate_count,
        "missing_count": latest_run.missing_count,
        
        # Operational KPIs
        "match_rate_pct": match_rate,
        "exception_rate_pct": exception_rate,
        "review_rate_pct": review_rate,
        "ai_escalation_rate_pct": ai_escalation_rate,
        "processing_time_ms": latest_run.processing_time_ms,
        "throughput_rps": latest_run.throughput_rps,
        
        # Financial Volumes
        "total_matched_volume": latest_run.total_matched_volume,
        "total_exception_volume": latest_run.total_exception_volume,
        "total_review_volume": latest_run.total_review_volume,
        "value_match_rate_pct": round((latest_run.total_matched_volume / total_volume) * 100, 2) if total_volume > 0 else 0.0,
        
        # AI Verification Stats
        "ai_verified_count": ai_verified_count,
        "ai_failed_count": ai_failed_count,
        
        # Visual breakdown structures
        "status_distribution": status_distribution,
        "exceptions_by_type": exceptions_by_type,
        "severity_distribution": severity_distribution,
        
        # Ground Truth Benchmarks
        "evaluation": {
            "has_evaluation": eval_record is not None,
            "accuracy": eval_record.accuracy if eval_record else None,
            "precision": eval_record.precision if eval_record else None,
            "recall": eval_record.recall if eval_record else None,
            "f1_score": eval_record.f1_score if eval_record else None,
            "false_positive_rate": eval_record.false_positive_rate if eval_record else None,
            "false_negative_rate": eval_record.false_negative_rate if eval_record else None,
            "exception_detection_accuracy": eval_record.exception_accuracy if eval_record else None,
            "true_positives": eval_record.true_positives if eval_record else None,
            "false_positives": eval_record.false_positives if eval_record else None,
            "false_negatives": eval_record.false_negatives if eval_record else None,
            "true_negatives": eval_record.true_negatives if eval_record else None,
        } if eval_record else None,
    }
