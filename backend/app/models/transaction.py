"""
Transaction models for Bank, Gateway, and Invoices.
"""

from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Float, Date, DateTime, ForeignKey, Index, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class BankTransaction(Base):
    """
    Represents a bank statement line item.
    Stores both raw input data and preprocessed normalized fields.
    """
    __tablename__ = "bank_transactions"

    bank_txn_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("reconciliation_runs.run_id"), nullable=True, index=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("datasets.id"), nullable=True, index=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(32), default="CREDIT") # CREDIT, DEBIT
    
    # Normalized fields for high-performance matching
    normalized_amount: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    normalized_date: Mapped[date] = mapped_column(Date, nullable=False)
    normalized_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    normalized_desc: Mapped[str] = mapped_column(Text, nullable=False)

    # Extended canonical fields
    value_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    utr: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    credit_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    debit_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(8), default="INR", nullable=True)
    balance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Raw content hash for idempotent ingestion deduplication
    raw_row_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("ix_bank_date_amount", "normalized_date", "normalized_amount"),
    )


class GatewayTransaction(Base):
    """
    Represents a payment gateway (e.g. Stripe, Razorpay) transaction record.
    """
    __tablename__ = "gateway_transactions"

    gateway_txn_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("reconciliation_runs.run_id"), nullable=True, index=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("datasets.id"), nullable=True, index=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    gross_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_amount_derived: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    customer_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    payment_reference: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="CAPTURED") # CAPTURED, FAILED, REFUNDED, PENDING

    # Extended canonical fields
    gateway_order_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # UPI, CARD, NET_BANKING, WALLET
    currency: Mapped[Optional[str]] = mapped_column(String(8), default="INR", nullable=True)
    gateway_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # razorpay, stripe, paytm
    
    # Normalized fields
    normalized_amount: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    normalized_date: Mapped[date] = mapped_column(Date, nullable=False)
    normalized_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    normalized_customer: Mapped[str] = mapped_column(String(256), nullable=False, index=True)

    # Decomposed fee settlement fields
    gateway_fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tax_on_fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_settlement: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Raw content hash for idempotent ingestion deduplication
    raw_row_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("ix_gw_date_amount", "normalized_date", "normalized_amount"),
    )


class Invoice(Base):
    """
    Represents an accounts receivable invoice record from the ERP / billing system.
    """
    __tablename__ = "invoices"

    invoice_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("reconciliation_runs.run_id"), nullable=True, index=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("datasets.id"), nullable=True, index=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    invoice_reference: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="ISSUED") # ISSUED, PAID, PARTIALLY_PAID, CANCELLED

    # Extended canonical fields
    order_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    customer_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    tax_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(8), default="INR", nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    # Normalized fields
    normalized_amount: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    normalized_date: Mapped[date] = mapped_column(Date, nullable=False)
    normalized_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    normalized_customer: Mapped[str] = mapped_column(String(256), nullable=False, index=True)

    # Raw content hash for idempotent ingestion deduplication
    raw_row_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("ix_inv_date_amount", "normalized_date", "normalized_amount"),
    )
