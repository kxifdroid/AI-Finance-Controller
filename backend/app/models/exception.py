"""
Exception models for tracking discrepancies, missing records, and workflow status.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ExceptionRecord(Base):
    """
    Represents an unresolved or anomalous financial record requiring operator investigation.
    Tracks severity, monetary exposure, and human review lifecycle.
    """
    __tablename__ = "exceptions"

    exception_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("reconciliation_runs.run_id"), nullable=False, index=True)
    
    bank_txn_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("bank_transactions.bank_txn_id"), nullable=True, index=True)
    gateway_txn_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("gateway_transactions.gateway_txn_id"), nullable=True, index=True)
    invoice_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("invoices.invoice_id"), nullable=True, index=True)
    
    exception_type: Mapped[str] = mapped_column(String(64), index=True)
    # Types: TIMING_DIFFERENCE, FEE_VARIANCE, AMOUNT_MISMATCH, NO_MATCH_FOUND,
    #        MISSING_ERP_TRANSACTION, MISSING_GATEWAY_TRANSACTION, MISSING_BANK_SETTLEMENT,
    #        DUPLICATE_TRANSACTION, FEE_MISMATCH, TAX_MISMATCH, DATE_MISMATCH,
    #        STATUS_MISMATCH, PARTIAL_SETTLEMENT, REFUND, MANY_TO_ONE_SETTLEMENT, UNKNOWN

    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM", index=True) # HIGH, MEDIUM, LOW
    amount_involved: Mapped[float] = mapped_column(Float, default=0.0)
    amount_discrepancy: Mapped[float] = mapped_column(Float, default=0.0)
    
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True) # OPEN, IN_REVIEW, RESOLVED, IGNORED
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Structured evidence and related records
    evidence_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    related_records_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    run: Mapped["ReconciliationRun"] = relationship("ReconciliationRun", back_populates="exceptions")
    bank_transaction: Mapped[Optional["BankTransaction"]] = relationship("BankTransaction")
    gateway_transaction: Mapped[Optional["GatewayTransaction"]] = relationship("GatewayTransaction")
    invoice: Mapped[Optional["Invoice"]] = relationship("Invoice")
