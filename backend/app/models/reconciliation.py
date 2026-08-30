"""
Reconciliation and Match models.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Index, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ReconciliationRun(Base):
    """
    Tracks an execution of the reconciliation pipeline.
    Captures overall throughput, metrics, and timestamps.
    """
    __tablename__ = "reconciliation_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("datasets.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING") # RUNNING, COMPLETED, FAILED
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    exception_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    missing_count: Mapped[int] = mapped_column(Integer, default=0)
    
    ai_escalation_count: Mapped[int] = mapped_column(Integer, default=0)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    processing_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    throughput_rps: Mapped[float] = mapped_column(Float, default=0.0)
    
    total_matched_volume: Mapped[float] = mapped_column(Float, default=0.0)
    total_exception_volume: Mapped[float] = mapped_column(Float, default=0.0)
    total_review_volume: Mapped[float] = mapped_column(Float, default=0.0)

    # Ingestion idempotency & duplicate tracking
    rows_ingested: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped_as_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    input_file_hashes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    dataset: Mapped[Optional["Dataset"]] = relationship("Dataset", back_populates="runs")
    matches: Mapped[List["Match"]] = relationship("Match", back_populates="run", cascade="all, delete-orphan")
    exceptions: Mapped[List["ExceptionRecord"]] = relationship("ExceptionRecord", back_populates="run", cascade="all, delete-orphan")
    evaluations: Mapped[List["EvaluationResult"]] = relationship("EvaluationResult", back_populates="run", cascade="all, delete-orphan")


class Match(Base):
    """
    Represents a reconciled match relationship between Bank, Gateway, and Invoice records.
    Stores multi-factor score decomposition and AI verification audit trail.
    """
    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("reconciliation_runs.run_id"), nullable=False, index=True)
    
    bank_txn_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("bank_transactions.bank_txn_id"), nullable=True, index=True)
    gateway_txn_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("gateway_transactions.gateway_txn_id"), nullable=True, index=True)
    invoice_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("invoices.invoice_id"), nullable=True, index=True)
    
    decision: Mapped[str] = mapped_column(String(32), index=True) # MATCH, REVIEW, EXCEPTION, DUPLICATE, MISSING
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW") # LOW, MEDIUM, HIGH
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(256), default="None required")

    # Match classification and evidence
    match_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    # Types: EXACT, REFERENCE, FUZZY, SETTLEMENT, MANY_TO_ONE, FEE_RECONCILED
    evidence_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Fee-aware reconciliation fields (populated when match_type == FEE_RECONCILED)
    fee_classification: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # Values: FEE_RECONCILED, FEE_VARIANCE, FEE_MISMATCH
    fee_breakdown_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON: {gross, fee, tax, expected_net, actual_bank_credit, variance}
    
    # Feature scores
    amount_similarity: Mapped[float] = mapped_column(Float, default=0.0)
    date_similarity: Mapped[float] = mapped_column(Float, default=0.0)
    reference_similarity: Mapped[float] = mapped_column(Float, default=0.0)
    customer_similarity: Mapped[float] = mapped_column(Float, default=0.0)
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    # AI flags
    verified_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_verification_status: Mapped[Optional[str]] = mapped_column(String(32), default="NOT_REQUIRED", nullable=True)
    ai_raw_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    run: Mapped["ReconciliationRun"] = relationship("ReconciliationRun", back_populates="matches")
    bank_transaction: Mapped[Optional["BankTransaction"]] = relationship("BankTransaction")
    gateway_transaction: Mapped[Optional["GatewayTransaction"]] = relationship("GatewayTransaction")
    invoice: Mapped[Optional["Invoice"]] = relationship("Invoice")
