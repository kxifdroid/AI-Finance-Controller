"""
Human Approval Mechanism for Sensitive Financial Actions.

This module implements the human-in-the-loop approval workflow for actions
that require explicit human authorization before execution. This ensures
that AI recommendations are validated by humans for sensitive operations.

CRITICAL PRINCIPLE:
THE LLM PROPOSES; DETERMINISTIC CODE DISPOSES.
All write/sensitive actions must go through human approval.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import Session, relationship
from enum import Enum
import uuid
import json

from app.db.session import Base


class ApprovalStatus(str, Enum):
    """Approval workflow status states."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ApprovalActionType(str, Enum):
    """Types of actions requiring human approval."""
    MARK_RECONCILED = "MARK_RECONCILED"
    WRITE_OFF_VARIANCE = "WRITE_OFF_VARIANCE"
    CREATE_ADJUSTMENT = "CREATE_ADJUSTMENT"
    EXPORT_FINAL_REPORT = "EXPORT_FINAL_REPORT"
    VOID_DUPLICATE = "VOID_DUPLICATE"
    MANUAL_MATCH = "MANUAL_MATCH"
    BULK_RESOLVE = "BULK_RESOLVE"
    APPLY_AI_SUGGESTION = "APPLY_AI_SUGGESTION"


class ApprovalRequest(Base):
    """
    Model for tracking approval requests for sensitive financial actions.
    
    Workflow:
    1. Agent/System proposes an action (creates PENDING request)
    2. Human reviews the proposal with evidence
    3. Human approves or rejects
    4. Only on approval, the action is executed
    """
    __tablename__ = "approval_requests"
    
    id = Column(String, primary_key=True, default=lambda: f"APR_{uuid.uuid4().hex[:10].upper()}")
    
    # What action is being requested
    action_type = Column(SQLEnum(ApprovalActionType), nullable=False)
    
    # Target entity
    entity_type = Column(String, nullable=False)  # exception, match, transaction
    entity_id = Column(String, nullable=False)
    
    # Who/what requested this
    requested_by = Column(String, default="AI_AGENT")  # AI_AGENT, SYSTEM, user_id
    
    # Current status
    status = Column(SQLEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    
    # The proposed action details
    proposal_summary = Column(Text, nullable=False)
    proposal_details = Column(JSON)  # Structured action parameters
    
    # AI investigation reference (if applicable)
    investigation_id = Column(String, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_recommendation = Column(String, nullable=True)
    
    # Evidence supporting the proposal
    evidence_json = Column(JSON)
    
    # Monetary impact
    amount_involved = Column(Float, default=0.0)
    
    # Human review fields
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)  # Optional expiration
    executed_at = Column(DateTime, nullable=True)  # When action was actually performed
    
    # Audit trail
    run_id = Column(String, nullable=True)


class ApprovalService:
    """
    Service for managing human approval workflow.
    """
    
    @staticmethod
    def create_approval_request(
        db: Session,
        action_type: ApprovalActionType,
        entity_type: str,
        entity_id: str,
        proposal_summary: str,
        proposal_details: Optional[Dict[str, Any]] = None,
        evidence: Optional[Dict[str, Any]] = None,
        amount_involved: float = 0.0,
        ai_confidence: Optional[float] = None,
        ai_recommendation: Optional[str] = None,
        investigation_id: Optional[str] = None,
        requested_by: str = "AI_AGENT",
        run_id: Optional[str] = None,
    ) -> ApprovalRequest:
        """
        Create a new approval request for a sensitive action.
        
        Args:
            db: Database session
            action_type: Type of action being requested
            entity_type: Type of entity (exception, match, transaction)
            entity_id: ID of the target entity
            proposal_summary: Human-readable summary of the proposal
            proposal_details: Structured parameters for the action
            evidence: Supporting evidence
            amount_involved: Monetary amount affected
            ai_confidence: AI confidence score (if AI-suggested)
            ai_recommendation: AI recommendation text
            investigation_id: Related AI investigation ID
            requested_by: Who/what is requesting (AI_AGENT, SYSTEM, user_id)
            run_id: Related reconciliation run ID
        
        Returns:
            Created ApprovalRequest
        """
        request = ApprovalRequest(
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            proposal_summary=proposal_summary,
            proposal_details=proposal_details or {},
            evidence_json=evidence or {},
            amount_involved=amount_involved,
            ai_confidence=ai_confidence,
            ai_recommendation=ai_recommendation,
            investigation_id=investigation_id,
            requested_by=requested_by,
            run_id=run_id,
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        
        # Log to audit trail
        from app.services.audit import AuditService
        AuditService.log(
            db=db,
            entity_type="approval_request",
            entity_id=request.id,
            action="created",
            rule_or_reason=f"Approval requested for {action_type.value} on {entity_type}/{entity_id}",
            actor=requested_by,
            before_status=None,
            after_status="PENDING",
        )
        
        return request
    
    @staticmethod
    def approve(
        db: Session,
        approval_id: str,
        reviewed_by: str,
        review_notes: Optional[str] = None,
        execute_action: bool = True,
    ) -> ApprovalRequest:
        """
        Approve a pending request and optionally execute the action.
        
        Args:
            db: Database session
            approval_id: ID of the approval request
            reviewed_by: User ID of the reviewer
            review_notes: Optional notes from the reviewer
            execute_action: Whether to immediately execute the approved action
        
        Returns:
            Updated ApprovalRequest
        """
        request = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
        if not request:
            raise ValueError(f"Approval request {approval_id} not found")
        
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot approve request in status {request.status}")
        
        request.status = ApprovalStatus.APPROVED
        request.reviewed_by = reviewed_by
        request.reviewed_at = datetime.now(timezone.utc)
        request.review_notes = review_notes
        
        db.commit()
        
        # Log to audit trail
        from app.services.audit import AuditService
        AuditService.log(
            db=db,
            entity_type="approval_request",
            entity_id=request.id,
            action="approved",
            rule_or_reason=f"Human approved {request.action_type.value}",
            actor=reviewed_by,
            before_status="PENDING",
            after_status="APPROVED",
        )
        
        # Execute the action if requested
        if execute_action:
            ApprovalService._execute_approved_action(db, request)
        
        db.refresh(request)
        return request
    
    @staticmethod
    def reject(
        db: Session,
        approval_id: str,
        reviewed_by: str,
        rejection_reason: str,
        review_notes: Optional[str] = None,
    ) -> ApprovalRequest:
        """
        Reject a pending request.
        
        Args:
            db: Database session
            approval_id: ID of the approval request
            reviewed_by: User ID of the reviewer
            rejection_reason: Reason for rejection (required)
            review_notes: Optional additional notes
        
        Returns:
            Updated ApprovalRequest
        """
        request = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
        if not request:
            raise ValueError(f"Approval request {approval_id} not found")
        
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot reject request in status {request.status}")
        
        request.status = ApprovalStatus.REJECTED
        request.reviewed_by = reviewed_by
        request.reviewed_at = datetime.now(timezone.utc)
        request.rejection_reason = rejection_reason
        request.review_notes = review_notes
        
        db.commit()
        
        # Log to audit trail
        from app.services.audit import AuditService
        AuditService.log(
            db=db,
            entity_type="approval_request",
            entity_id=request.id,
            action="rejected",
            rule_or_reason=f"Human rejected: {rejection_reason}",
            actor=reviewed_by,
            before_status="PENDING",
            after_status="REJECTED",
        )
        
        db.refresh(request)
        return request
    
    @staticmethod
    def _execute_approved_action(db: Session, request: ApprovalRequest) -> None:
        """
        Execute the approved action based on action type.
        
        This is where the actual financial action is performed AFTER human approval.
        """
        action_type = request.action_type
        entity_type = request.entity_type
        entity_id = request.entity_id
        details = request.proposal_details or {}
        
        try:
            if action_type == ApprovalActionType.MARK_RECONCILED:
                # Mark an exception as reconciled/resolved
                from app.models.exception import ExceptionRecord
                exception = db.query(ExceptionRecord).filter(
                    ExceptionRecord.exception_id == entity_id
                ).first()
                if exception:
                    exception.status = "RESOLVED"
                    exception.resolved_by = request.reviewed_by
                    exception.notes = f"Approved via {request.id}: {request.review_notes or 'Human approved'}"
                    exception.updated_at = datetime.utcnow()
            
            elif action_type == ApprovalActionType.VOID_DUPLICATE:
                # Mark duplicate transaction for void/reversal
                from app.models.exception import ExceptionRecord
                exception = db.query(ExceptionRecord).filter(
                    ExceptionRecord.exception_id == entity_id
                ).first()
                if exception:
                    exception.status = "RESOLVED"
                    exception.notes = f"Duplicate voided via {request.id}"
                    exception.updated_at = datetime.utcnow()
            
            elif action_type == ApprovalActionType.APPLY_AI_SUGGESTION:
                # Apply AI-suggested resolution
                from app.models.exception import ExceptionRecord
                exception = db.query(ExceptionRecord).filter(
                    ExceptionRecord.exception_id == entity_id
                ).first()
                if exception:
                    recommendation = request.ai_recommendation or "MARK_RECONCILED"
                    if recommendation == "MARK_RECONCILED":
                        exception.status = "RESOLVED"
                    elif recommendation == "ESCALATE":
                        exception.status = "IN_REVIEW"
                    exception.notes = f"AI suggestion applied via {request.id} (confidence: {request.ai_confidence})"
                    exception.updated_at = datetime.utcnow()
            
            # TODO: Add more action handlers as needed
            
            request.executed_at = datetime.utcnow()
            db.commit()
            
            # Log execution
            from app.services.audit import AuditService
            AuditService.log(
                db=db,
                entity_type=entity_type,
                entity_id=entity_id,
                action=f"executed_{action_type.value.lower()}",
                rule_or_reason=f"Executed via approval {request.id}",
                actor=request.reviewed_by,
                after_status="EXECUTED",
            )
            
        except Exception as e:
            # Log execution failure
            from app.services.audit import AuditService
            AuditService.log(
                db=db,
                entity_type="approval_request",
                entity_id=request.id,
                action="execution_failed",
                rule_or_reason=f"Execution failed: {str(e)}",
                actor="SYSTEM",
            )
            raise
    
    @staticmethod
    def get_pending_approvals(
        db: Session,
        action_type: Optional[ApprovalActionType] = None,
        entity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ApprovalRequest]:
        """
        Get pending approval requests with optional filters.
        """
        query = db.query(ApprovalRequest).filter(
            ApprovalRequest.status == ApprovalStatus.PENDING
        )
        
        if action_type:
            query = query.filter(ApprovalRequest.action_type == action_type)
        if entity_type:
            query = query.filter(ApprovalRequest.entity_type == entity_type)
        
        return query.order_by(ApprovalRequest.created_at.desc()).offset(offset).limit(limit).all()
    
    @staticmethod
    def get_approval_history(
        db: Session,
        entity_id: Optional[str] = None,
        reviewed_by: Optional[str] = None,
        limit: int = 100,
    ) -> List[ApprovalRequest]:
        """
        Get approval history with optional filters.
        """
        query = db.query(ApprovalRequest)
        
        if entity_id:
            query = query.filter(ApprovalRequest.entity_id == entity_id)
        if reviewed_by:
            query = query.filter(ApprovalRequest.reviewed_by == reviewed_by)
        
        return query.order_by(ApprovalRequest.created_at.desc()).limit(limit).all()
