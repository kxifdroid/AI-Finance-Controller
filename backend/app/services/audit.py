import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.models.audit import AuditLog


class AuditService:
    @staticmethod
    def log(
        db: Session,
        entity_type: str,
        entity_id: str,
        action: str,
        rule_or_reason: str,
        actor: str = "system",
        before_status: Optional[str] = None,
        after_status: Optional[str] = None,
    ) -> AuditLog:
        log_entry = AuditLog(
            log_id=f"LOG_{uuid.uuid4().hex[:12].upper()}",
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            rule_or_reason=rule_or_reason,
            actor=actor,
            before_status=before_status,
            after_status=after_status,
            timestamp=datetime.now(),
        )
        db.add(log_entry)
        return log_entry
