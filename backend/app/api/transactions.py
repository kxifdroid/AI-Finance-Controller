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
from app.services.scoring import ScoringService
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


from app.services.scoring import ScoringService


def compute_match_features(match_record: Match, bank: Optional[Any], gw: Optional[Any], inv: Optional[Any]) -> Dict[str, float]:
    scorer = ScoringService()

    # 1. Handle Many-to-One Batch Settlement
    if match_record.match_type == "MANY_TO_ONE":
        return {
            "amount_similarity": 1.0,
            "date_similarity": 1.0,
            "reference_similarity": 1.0,
            "customer_similarity": 1.0,
            "composite_score": round(match_record.confidence_score, 4),
        }

    # 2. Extract numeric and string values
    inv_amt = float(getattr(inv, "amount", 0.0) or 0.0)
    gw_amt = float(getattr(gw, "amount", 0.0) or 0.0)
    gw_fee = float(getattr(gw, "gateway_fee", 0.0) or 0.0)
    gw_tax = float(getattr(gw, "tax_on_fee", 0.0) or 0.0)
    gw_net = float(getattr(gw, "net_settlement", 0.0) or (gw_amt - gw_fee - gw_tax if gw_amt > 0 else 0.0))
    bank_amt = float(getattr(bank, "amount", 0.0) or 0.0)

    # 3. AMOUNT SIMILARITY (3-Way)
    # Leg 1: Invoice vs Gateway
    amt_sim_1 = scorer.calculate_amount_similarity(inv_amt, gw_amt) if (inv and gw) else (1.0 if not inv else 0.0)

    # Leg 2: Gateway vs Bank (If Bank is missing, bank_amt is 0 -> amt_sim_2 is 0.0)
    if gw and bank:
        amt_sim_2 = scorer.calculate_amount_similarity(gw_net if gw_net > 0 else gw_amt, bank_amt)
    elif gw and not bank:
        # Missing Bank Settlement: No money has settled into bank
        amt_sim_2 = 0.0
    elif inv and not gw and bank:
        amt_sim_2 = scorer.calculate_amount_similarity(inv_amt, bank_amt)
    else:
        amt_sim_2 = 0.0

    amount_sim = round(min(amt_sim_1, amt_sim_2), 4)

    # 4. REFERENCE SIMILARITY
    inv_ref = getattr(inv, "invoice_reference", "")
    gw_ref = getattr(gw, "payment_reference", "")
    bank_ref = getattr(bank, "reference", "")
    bank_desc = getattr(bank, "description", "")

    ref_sim_1 = scorer.calculate_reference_similarity(inv_ref, gw_ref) if (inv and gw) else 1.0
    ref_sim_2 = (
        max(scorer.calculate_reference_similarity(gw_ref, bank_ref), scorer.calculate_description_similarity(bank_desc, "", gw_ref))
        if (gw and bank)
        else (1.0 if not bank else scorer.calculate_reference_similarity(inv_ref, bank_ref))
    )
    reference_sim = round(min(ref_sim_1, ref_sim_2), 4)

    # 5. DATE SIMILARITY
    inv_date = getattr(inv, "invoice_date", None)
    gw_date = getattr(gw, "transaction_date", None)
    bank_date = getattr(bank, "transaction_date", None)

    date_sim_1 = scorer.calculate_date_similarity(inv_date, gw_date) if (inv and gw and inv_date and gw_date) else 1.0
    date_sim_2 = (
        scorer.calculate_date_similarity(gw_date, bank_date)
        if (gw and bank and gw_date and bank_date)
        else (0.50 if not bank else 1.0) # 0.50 indicates pending clearance lag
    )
    date_sim = round(min(date_sim_1, date_sim_2), 4)

    # 6. CUSTOMER SIMILARITY
    inv_cust = getattr(inv, "customer_name", "")
    gw_cust = getattr(gw, "customer_name", "")
    cust_sim = scorer.calculate_customer_similarity(inv_cust, gw_cust) if (inv and gw) else (
        scorer.calculate_description_similarity(bank_desc, gw_cust or inv_cust, "") if (bank and (gw_cust or inv_cust)) else 1.0
    )
    customer_sim = round(cust_sim, 4)

    # 7. Compute Composite Score
    computed = scorer.compute_match_score(amount_sim, date_sim, reference_sim, customer_sim)
    features = computed["features"]
    features["composite_score"] = round(match_record.confidence_score or computed["score"], 4)
    return features


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

    features = compute_match_features(match_record, bank, gw, inv)

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
        features=features,
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
