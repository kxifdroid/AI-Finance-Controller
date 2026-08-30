"""
Exception Management Service.

Problem Solved:
Captures, classifies, and tracks all financial discrepancies, un-reconciled items,
and audit anomalies that cannot be safely auto-matched across the expanded exception taxonomy.

Why It Exists:
To provide a dedicated triage workflow for human finance operators with clear
explanations, monetary exposure calculations, structured evidence chains, and resolution tracking.

Input:
Discrepant transaction triplets/pairs, evidence payloads, and classification metadata.

Output:
Persisted ExceptionRecord entities with structured evidence and state transition management
(OPEN -> IN_REVIEW -> RESOLVED / IGNORED).
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.config import settings
from app.models.exception import ExceptionRecord
from app.services.reconciliation.evidence import EvidenceBuilder


# Expanded canonical exception taxonomy
VALID_EXCEPTION_TYPES = {
    "MISSING_ERP_TRANSACTION",
    "MISSING_GATEWAY_TRANSACTION",
    "MISSING_BANK_SETTLEMENT",
    "DUPLICATE_TRANSACTION",
    "FEE_MISMATCH",
    "TAX_MISMATCH",
    "DATE_MISMATCH",
    "MANY_TO_ONE_SETTLEMENT",
    "PARTIAL_SETTLEMENT",
    "REFUND",
    "TIMING_DIFFERENCE",
    "FEE_VARIANCE",
    "AMOUNT_MISMATCH",
    "NO_MATCH_FOUND",
    "STATUS_MISMATCH",
    "UNKNOWN",
}


class ExceptionService:
    """
    Service for creating, classifying, and updating financial exceptions with structured evidence.
    """

    @staticmethod
    def classify_and_create_exception(
        db: Session,
        run_id: str,
        bank_record: Optional[Any] = None,
        gateway_record: Optional[Any] = None,
        invoice_record: Optional[Any] = None,
        decision: str = "EXCEPTION",
        reason: str = "",
        recommended_action: str = "",
        suggested_type: Optional[str] = None,
        suggested_severity: Optional[str] = None,
        is_timing_difference: bool = False,
        evidence_json: Optional[str] = None,
        related_records_json: Optional[str] = None,
    ) -> ExceptionRecord:
        """
        Analyzes transaction properties to classify into the canonical exception taxonomy,
        populates structured evidence chains, and persists the exception record.

        Supported Exception Types:
        - MISSING_ERP_TRANSACTION: Bank or Gateway transaction has no ERP invoice.
        - MISSING_GATEWAY_TRANSACTION: Invoice or Bank transaction missing gateway record.
        - MISSING_BANK_SETTLEMENT: Invoiced and captured payment has not settled in bank.
        - DUPLICATE_TRANSACTION: Multiple identical records detected within the same source.
        - FEE_MISMATCH: Gateway fee discrepancy exceeds permissible tolerance.
        - TAX_MISMATCH: GST / VAT on gateway fee does not match standard 18% calculation.
        - DATE_MISMATCH: Counterparts match on reference/amount but exceed date window.
        - TIMING_DIFFERENCE: Matched amount/ref but outside tolerance date window.
        - FEE_VARIANCE: Gateway fee variance matches configured tolerance (1%–5%).
        - AMOUNT_MISMATCH: Reference matches but amount differs.
        - NO_MATCH_FOUND: General missing counterpart record.
        - PARTIAL_SETTLEMENT: Settlement amount is only a fraction of expected gross.
        - REFUND: Reversal or refund record requiring separate reconciliation.
        - MANY_TO_ONE_SETTLEMENT: Batch settlement grouping requiring supervisor review.
        """
        b_id = getattr(bank_record, "bank_txn_id", None)
        g_id = getattr(gateway_record, "gateway_txn_id", None)
        i_id = getattr(invoice_record, "invoice_id", None)

        b_amt = float(getattr(bank_record, "amount", 0.0) or 0.0)
        g_amt = float(getattr(gateway_record, "amount", 0.0) or 0.0)
        i_amt = float(getattr(invoice_record, "amount", 0.0) or 0.0)

        amounts = [a for a in (b_amt, g_amt, i_amt) if a != 0.0]
        max_amt = max(abs(a) for a in amounts) if amounts else 0.0
        discrepancy = 0.0

        if suggested_type:
            exc_type = suggested_type
            if not reason:
                reason = f"Exception classified as {suggested_type}."
            if not recommended_action:
                recommended_action = "Investigate discrepancy in transaction ledger."
            if b_amt != 0.0 and g_amt != 0.0:
                discrepancy = round(abs(g_amt - b_amt), 2)
            elif i_amt != 0.0 and g_amt != 0.0:
                discrepancy = round(abs(i_amt - g_amt), 2)
            elif max_amt > 0:
                discrepancy = round(max_amt, 2)
        elif is_timing_difference:
            exc_type = "TIMING_DIFFERENCE"
            reason = reason or "Counterpart matched reference and amount but date fell outside tolerance window."
            recommended_action = recommended_action or "Review timing discrepancy / clearance lag."
        elif (not b_id and not g_id) or (not b_id and not i_id) or (not g_id and not i_id):
            exc_type = "NO_MATCH_FOUND"
            missing_parts = []
            if not b_id:
                missing_parts.append("Bank")
            if not g_id:
                missing_parts.append("Gateway")
            if not i_id:
                missing_parts.append("Invoice")
            reason = reason or f"No counterpart record found. Missing: {', '.join(missing_parts)}."
            recommended_action = recommended_action or f"Locate missing counterpart in {', '.join(missing_parts)}."
            discrepancy = round(max_amt, 2)
        else:
            # Pair or Triplet present with amount differences
            if b_amt != 0.0 and g_amt != 0.0:
                discrepancy = round(abs(g_amt - b_amt), 2)
                fee_pct = (g_amt - b_amt) / g_amt if g_amt > 0 else 0.0
                if settings.FEE_VARIANCE_MIN_PCT <= fee_pct <= settings.FEE_VARIANCE_MAX_PCT:
                    exc_type = "FEE_VARIANCE"
                    reason = reason or f"Payment gateway fee deduction of {round(fee_pct * 100, 2)}% (Gross: ₹{g_amt:,.2f}, Net: ₹{b_amt:,.2f})."
                    recommended_action = recommended_action or "Approve variance as standard payment gateway processing fee."
                else:
                    exc_type = "AMOUNT_MISMATCH"
                    diff = abs(b_amt - g_amt)
                    reason = reason or f"Amount discrepancy detected between Bank (₹{b_amt:,.2f}) and Gateway (₹{g_amt:,.2f}) with a delta of ₹{diff:,.2f}."
                    recommended_action = recommended_action or f"Review settlement breakdown for ₹{diff:,.2f} discrepancy."
            elif i_amt != 0.0 and g_amt != 0.0:
                discrepancy = round(abs(i_amt - g_amt), 2)
                exc_type = "AMOUNT_MISMATCH"
                if g_amt < i_amt:
                    reason = reason or f"Underpayment detected: ERP Invoice billed ₹{i_amt:,.2f}, but Gateway only captured ₹{g_amt:,.2f} (short by ₹{discrepancy:,.2f})."
                    recommended_action = recommended_action or f"Request balance payment of ₹{discrepancy:,.2f} or issue a debit note."
                else:
                    reason = reason or f"Overpayment detected: ERP Invoice billed ₹{i_amt:,.2f}, but Gateway captured ₹{g_amt:,.2f} (overpaid by ₹{discrepancy:,.2f})."
                    recommended_action = recommended_action or f"Review overpayment of ₹{discrepancy:,.2f} and issue customer credit note."
            else:
                exc_type = "AMOUNT_MISMATCH"
                reason = reason or "Monetary discrepancy detected across transaction records."
                recommended_action = recommended_action or "Review ledger records to identify source of variance."

        # Determine severity from centralized thresholds
        if suggested_severity:
            severity = suggested_severity
        elif max_amt >= settings.SEVERITY_HIGH_THRESHOLD or discrepancy >= settings.SEVERITY_MEDIUM_THRESHOLD:
            severity = "HIGH"
        elif max_amt >= settings.SEVERITY_MEDIUM_THRESHOLD or discrepancy >= settings.SEVERITY_LOW_THRESHOLD:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # Build related records JSON if not provided
        if not related_records_json:
            related_dict = {
                "bank_txn_id": b_id,
                "gateway_txn_id": g_id,
                "invoice_id": i_id,
            }
            related_records_json = json.dumps({k: v for k, v in related_dict.items() if v is not None})

        # Build structured evidence JSON if not provided
        if not evidence_json:
            evidence_json = EvidenceBuilder.build_exception_evidence(
                exception_type=exc_type,
                reason=reason,
                amounts={
                    "amount_involved": round(max_amt, 2),
                    "amount_discrepancy": round(discrepancy, 2),
                    "bank_amount": b_amt,
                    "gateway_amount": g_amt,
                    "invoice_amount": i_amt,
                },
                dates={
                    "bank_date": str(getattr(bank_record, "transaction_date", "")),
                    "gateway_date": str(getattr(gateway_record, "transaction_date", "")),
                    "invoice_date": str(getattr(invoice_record, "invoice_date", "")),
                },
                references={
                    "bank_ref": getattr(bank_record, "reference", ""),
                    "gateway_ref": getattr(gateway_record, "payment_reference", ""),
                    "invoice_ref": getattr(invoice_record, "invoice_reference", ""),
                },
                policy_citation="Financial Controller Standard Operating Procedure 4.2 - Discrepancy Escalation",
            )

        exc_record = ExceptionRecord(
            exception_id=f"EXC_{uuid.uuid4().hex[:10].upper()}",
            run_id=run_id,
            bank_txn_id=b_id,
            gateway_txn_id=g_id,
            invoice_id=i_id,
            exception_type=exc_type,
            severity=severity,
            amount_involved=round(max_amt, 2),
            amount_discrepancy=round(discrepancy, 2),
            explanation=reason,
            recommended_action=recommended_action,
            status="OPEN",
            evidence_json=evidence_json,
            related_records_json=related_records_json,
        )
        db.add(exc_record)
        return exc_record

    @staticmethod
    def update_exception_status(
        db: Session,
        exception_id: str,
        status: str,
        notes: Optional[str] = None,
        resolved_by: Optional[str] = "Operator",
    ) -> Optional[ExceptionRecord]:
        """
        Transitions the lifecycle status of an exception (OPEN, IN_REVIEW, RESOLVED, IGNORED).
        """
        record = db.query(ExceptionRecord).filter(ExceptionRecord.exception_id == exception_id).first()
        if not record:
            return None

        record.status = status.upper()
        if notes is not None:
            record.notes = notes
        if resolved_by:
            record.resolved_by = resolved_by
        record.updated_at = datetime.now()

        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def get_exceptions(
        db: Session,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ExceptionRecord]:
        """
        Fetches filtered exception records ordered by severity and creation date.
        """
        query = db.query(ExceptionRecord)
        if status:
            query = query.filter(ExceptionRecord.status == status.upper())
        if severity:
            query = query.filter(ExceptionRecord.severity == severity.upper())

        return query.order_by(desc(ExceptionRecord.created_at)).offset(offset).limit(limit).all()
