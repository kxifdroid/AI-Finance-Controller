from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = 'audit_log'

    log_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    rule_or_reason: Mapped[str] = mapped_column(String(256))
    actor: Mapped[str] = mapped_column(String(64), default='system')
    before_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    after_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
