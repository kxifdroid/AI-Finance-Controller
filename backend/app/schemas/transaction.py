"""
Pydantic schemas for Bank, Gateway, and Invoice transactions.
"""

from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class BankTransactionBase(BaseModel):
    bank_txn_id: str
    transaction_date: date
    amount: float
    description: str
    reference: str
    transaction_type: str = "CREDIT"


class BankTransactionResponse(BankTransactionBase):
    run_id: Optional[str] = None
    normalized_amount: float
    normalized_date: date
    normalized_ref: str
    normalized_desc: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GatewayTransactionBase(BaseModel):
    gateway_txn_id: str
    transaction_date: date
    amount: float
    customer_name: str
    payment_reference: str
    status: str = "CAPTURED"
    gateway_fee: Optional[float] = None
    tax_on_fee: Optional[float] = None
    net_settlement: Optional[float] = None


class GatewayTransactionResponse(GatewayTransactionBase):
    run_id: Optional[str] = None
    normalized_amount: float
    normalized_date: date
    normalized_ref: str
    normalized_customer: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceBase(BaseModel):
    invoice_id: str
    invoice_date: date
    customer_name: str
    amount: float
    invoice_reference: str
    status: str = "ISSUED"


class InvoiceResponse(InvoiceBase):
    run_id: Optional[str] = None
    normalized_amount: float
    normalized_date: date
    normalized_ref: str
    normalized_customer: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionDetailResponse(BaseModel):
    """3-Way side-by-side transaction detail view."""
    match_id: str
    decision: str
    confidence_score: float
    risk_level: str
    explanation: str
    recommended_action: str
    verified_by_ai: bool = False
    ai_raw_response: Optional[str] = None

    # Fee-aware reconciliation fields
    fee_classification: Optional[str] = None
    fee_breakdown_json: Optional[str] = None

    features: Dict[str, float]
    
    bank_record: Optional[BankTransactionResponse] = None
    gateway_record: Optional[GatewayTransactionResponse] = None
    invoice_record: Optional[InvoiceResponse] = None
    exception_record: Optional[Dict[str, Any]] = None
