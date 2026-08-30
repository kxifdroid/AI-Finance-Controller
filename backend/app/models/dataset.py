"""
Dataset and FileRecord models.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Dataset(Base):
    """
    Represents a logical collection of uploaded financial files (Bank, Gateway, Invoices)
    forming a single batch of records for reconciliation.
    """
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="UPLOADED") # UPLOADED, PROCESSED, FAILED
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    files: Mapped[List["FileRecord"]] = relationship("FileRecord", back_populates="dataset", cascade="all, delete-orphan")
    runs: Mapped[List["ReconciliationRun"]] = relationship("ReconciliationRun", back_populates="dataset")


class FileRecord(Base):
    """
    Represents an individual uploaded file (Excel, CSV, PDF) within a Dataset.
    """
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    dataset_id: Mapped[str] = mapped_column(String(64), ForeignKey("datasets.id"), nullable=False, index=True)
    
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False) # csv, xlsx, pdf
    data_type: Mapped[str] = mapped_column(String(32), nullable=False) # BANK, GATEWAY, INVOICE, UNKNOWN
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    mapping_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # JSON serialized mapping
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="files")
