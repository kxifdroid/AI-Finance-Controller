"""
Cash forecast models.
"""

from datetime import datetime, date
from sqlalchemy import String, Float, Integer, Date, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class CashFlow(Base):
    """
    Stores 7-day rule-based cash forecast points.
    """
    __tablename__ = "cash_flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    day_offset: Mapped[int] = mapped_column(Integer, nullable=False) # 0, 1, 3, 7
    
    cleared_cash: Mapped[float] = mapped_column(Float, default=0.0)
    expected_settlements: Mapped[float] = mapped_column(Float, default=0.0)
    expected_receivables: Mapped[float] = mapped_column(Float, default=0.0)
    upcoming_payouts: Mapped[float] = mapped_column(Float, default=0.0)
    recurring_expenses: Mapped[float] = mapped_column(Float, default=0.0)
    projected_balance: Mapped[float] = mapped_column(Float, default=0.0)
    
    confidence_level: Mapped[str] = mapped_column(String(16), default="HIGH") # HIGH, MEDIUM, LOW
    assumptions_notes: Mapped[str] = mapped_column(Text, default="")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
