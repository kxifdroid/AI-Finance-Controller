"""
Pydantic schemas for exception triage and resolution workflows.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, ConfigDict
from app.schemas.transaction import BankTransactionResponse, GatewayTransactionResponse, InvoiceResponse


class AIInvestigationResponse(BaseModel):
    investigation_id: str
    exception_id: str
    run_id: str
    classification: str
    confidence: float
    explanation: str
    evidence: Union[List[str], Dict[str, Any]]
    recommendation: str # MARK_RECONCILED | MANUAL_REVIEW | ESCALATE
    requires_human_review: bool
    deterministic_override: bool
    override_reason: Optional[str] = None
    policy_references: Optional[List[str]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExceptionResponse(BaseModel):
    exception_id: str
    run_id: str
    bank_txn_id: Optional[str] = None
    gateway_txn_id: Optional[str] = None
    invoice_id: Optional[str] = None
    exception_type: str
    severity: str
    amount_involved: float
    amount_discrepancy: float
    explanation: str
    recommended_action: str
    status: str
    notes: Optional[str] = None
    resolved_by: Optional[str] = None
    evidence_json: Optional[str] = None
    related_records_json: Optional[str] = None
    investigation: Optional[AIInvestigationResponse] = None
    created_at: datetime
    updated_at: datetime

    bank_transaction: Optional[BankTransactionResponse] = None
    gateway_transaction: Optional[GatewayTransactionResponse] = None
    invoice: Optional[InvoiceResponse] = None

    model_config = ConfigDict(from_attributes=True)


class UpdateExceptionStatusRequest(BaseModel):
    status: str # OPEN, IN_REVIEW, RESOLVED, IGNORED
    notes: Optional[str] = None
    resolved_by: Optional[str] = "Operator"


class ApproveExceptionRequest(BaseModel):
    notes: Optional[str] = None


class RejectExceptionRequest(BaseModel):
    reason: str


class ExceptionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[ExceptionResponse]


