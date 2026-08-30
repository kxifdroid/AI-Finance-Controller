"""
Transaction and Match Explorer API Routes.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.db.session import get_db
from app.models.reconciliation import Match
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.models.exception import ExceptionRecord
from app.schemas.reconciliation import MatchResponse, MatchListResponse
from app.schemas.transaction import (
    TransactionDetailResponse,
    BankTransactionResponse,
    GatewayTransactionResponse,
    InvoiceResponse,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("", response_model=MatchListResponse)
def list_transactions(
    status: Optional[str] = Query(None, description="MATCH, REVIEW, EXCEPTION, DUPLICATE, MISSING"),
    risk: Optional[str] = Query(None, description="LOW, MEDIUM, HIGH"),
    search: Optional[str] = Query(None, description="Search term for ID, ref, or customer"),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Returns paginated transaction matches with comprehensive filtering.
    """
    query = db.query(Match)

    if status:
        query = query.filter(Match.decision == status.upper())
    if risk:
        query = query.filter(Match.risk_level == risk.upper())

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Match.bank_txn_id.ilike(s),
                Match.gateway_txn_id.ilike(s),
                Match.invoice_id.ilike(s),
                Match.explanation.ilike(s),
            )
        )

    total = query.count()
    offset = (page - 1) * page_size
    records = query.order_by(desc(Match.created_at)).offset(offset).limit(page_size).all()

    items = [MatchResponse.model_validate(r) for r in records]

    return MatchListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 1,
        items=items,
    )


@router.get("/{id}", response_model=TransactionDetailResponse)
def get_transaction_detail(
    id: str,
    db: Session = Depends(get_db),
):
    """
    Returns 3-way side-by-side reconciliation comparison for a specific transaction or match.
    """
    match_record = db.query(Match).filter(
        or_(
            Match.match_id == id,
            Match.bank_txn_id == id,
            Match.gateway_txn_id == id,
            Match.invoice_id == id,
        )
    ).first()

    if not match_record:
        raise HTTPException(status_code=404, detail="Transaction match record not found")

    bank = match_record.bank_transaction
    gw = match_record.gateway_transaction
    inv = match_record.invoice

    exc_record = db.query(ExceptionRecord).filter(
        or_(
            ExceptionRecord.bank_txn_id == match_record.bank_txn_id,
            ExceptionRecord.gateway_txn_id == match_record.gateway_txn_id,
            ExceptionRecord.invoice_id == match_record.invoice_id,
        )
    ).first()

    return TransactionDetailResponse(
        match_id=match_record.match_id,
        decision=match_record.decision,
        confidence_score=match_record.confidence_score,
        risk_level=match_record.risk_level,
        explanation=match_record.explanation,
        recommended_action=match_record.recommended_action,
        verified_by_ai=match_record.verified_by_ai,
        ai_raw_response=match_record.ai_raw_response,
        fee_classification=match_record.fee_classification,
        fee_breakdown_json=match_record.fee_breakdown_json,
        features={
            "amount_similarity": match_record.amount_similarity,
            "date_similarity": match_record.date_similarity,
            "reference_similarity": match_record.reference_similarity,
            "customer_similarity": match_record.customer_similarity,
            "composite_score": match_record.composite_score,
        },
        bank_record=BankTransactionResponse.model_validate(bank) if bank else None,
        gateway_record=GatewayTransactionResponse.model_validate(gw) if gw else None,
        invoice_record=InvoiceResponse.model_validate(inv) if inv else None,
        exception_record={
            "exception_id": exc_record.exception_id,
            "type": exc_record.exception_type,
            "severity": exc_record.severity,
            "amount_involved": exc_record.amount_involved,
            "amount_discrepancy": exc_record.amount_discrepancy,
            "explanation": exc_record.explanation,
            "status": exc_record.status,
        } if exc_record else None,
    )
