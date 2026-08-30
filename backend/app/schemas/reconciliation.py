"""
Pydantic schemas for reconciliation runs, matches, and pipeline triggers.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.transaction import BankTransactionResponse, GatewayTransactionResponse, InvoiceResponse


class RunReconciliationRequest(BaseModel):
    use_ai: bool = Field(default=True, description="Enable AI verification for ambiguous matches")
    dataset_id: Optional[str] = None
    amount_tolerance_pct: Optional[float] = None
    date_tolerance_days: Optional[int] = None
    auto_match_threshold: Optional[float] = None
    ai_review_threshold: Optional[float] = None


class ReconciliationRunResponse(BaseModel):
    run_id: str
    dataset_id: Optional[str] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_records: int
    matched_count: int
    review_count: int
    exception_count: int
    duplicate_count: int
    missing_count: int
    ai_escalation_count: int
    processing_time_ms: float
    throughput_rps: float
    total_matched_volume: float
    total_exception_volume: float
    total_review_volume: float
    rows_ingested: int = 0
    rows_skipped_as_duplicate: int = 0

    model_config = ConfigDict(from_attributes=True)


class MatchResponse(BaseModel):
    match_id: str
    run_id: str
    topology: str = "ONE_TO_ONE"
    reason_code: Optional[str] = None
    bank_txn_id: Optional[str] = None
    gateway_txn_id: Optional[str] = None
    invoice_id: Optional[str] = None
    primary_amount: float = 0.0
    expected_amount: float = 0.0
    settled_amount: float = 0.0
    variance_amount: float = 0.0
    amounts_json: Optional[str] = None
    decision: str
    confidence_score: float
    deterministic_confidence: float = 1.0
    risk_level: str
    explanation: str
    recommended_action: str
    match_type: Optional[str] = None
    evidence_json: Optional[str] = None
    amount_similarity: float
    date_similarity: float
    reference_similarity: float
    customer_similarity: float
    composite_score: float
    verified_by_ai: bool = False
    ai_verification_status: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_explanation: Optional[str] = None
    ai_raw_response: Optional[str] = None
    created_at: datetime

    bank_transaction: Optional[BankTransactionResponse] = None
    gateway_transaction: Optional[GatewayTransactionResponse] = None
    invoice: Optional[InvoiceResponse] = None

    model_config = ConfigDict(from_attributes=True)


class MatchListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[MatchResponse]


class MetricsSummaryResponse(BaseModel):
    run_id: Optional[str] = None
    dataset_id: Optional[str] = None
    total_records: int = 0
    matched_count: int = 0
    review_count: int = 0
    exception_count: int = 0
    duplicate_count: int = 0
    missing_count: int = 0
    
    # Financial Volumes
    total_volume: float = 0.0
    matched_volume: float = 0.0
    exception_volume: float = 0.0
    review_volume: float = 0.0
    
    # Operational metrics
    match_rate: float = 0.0
    exception_rate: float = 0.0
    ai_escalation_rate: float = 0.0
    processing_time_ms: float = 0.0
    throughput_rps: float = 0.0
    
    # Ground truth benchmark metrics (if ground truth available)
    has_ground_truth: bool = False
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    false_positive_rate: Optional[float] = None
    false_negative_rate: Optional[float] = None
    exception_detection_accuracy: Optional[float] = None
