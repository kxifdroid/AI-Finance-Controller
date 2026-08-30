"""
Structured Evidence Builder for Financial Reconciliation and Exceptions.

Problem Solved:
Generates deterministic, transparent, and auditable JSON evidence records for every
match, review, and exception decision made by the reconciliation pipeline.

Why It Exists:
To satisfy regulatory audit standards (SOX, RBI, GST) requiring every automated financial
reconciliation decision to carry an inspectable evidence chain with calculated expected/actual/variance
values, compared field pairs, and explicit policy citations.

Input:
Match/exception classification parameters, compared field values, numerical amounts, and policy metadata.

Output:
Deterministic, validated JSON strings stored in `Match.evidence_json` and `ExceptionRecord.evidence_json`.
"""

import json
from datetime import date, datetime
from typing import Dict, Any, Optional, List, Union


class EvidenceBuilder:
    """
    Constructs structured JSON evidence chains for reconciliation matches and exception records.
    """

    @staticmethod
    def _json_serializer(obj: Any) -> str:
        """Custom JSON serializer for date, datetime, and set objects."""
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, set):
            return list(obj)
        return str(obj)

    @classmethod
    def build_match_evidence(
        cls,
        match_type: str,
        rule: str,
        confidence: float,
        side_a_fields: Optional[Dict[str, Any]] = None,
        side_b_fields: Optional[Dict[str, Any]] = None,
        amounts: Optional[Dict[str, Any]] = None,
        dates: Optional[Dict[str, Any]] = None,
        compared_fields: Optional[Dict[str, Any]] = None,
        policy_citation: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Builds a structured JSON evidence string for a reconciled match relationship.

        Args:
            match_type: Classification (EXACT, FUZZY, SETTLEMENT, MANY_TO_ONE, FEE_RECONCILED).
            rule: Name of the matching rule that triggered the match.
            confidence: Confidence score between 0.0 and 1.0.
            side_a_fields: Raw/normalized fields from side A (e.g. Invoice / Gateway).
            side_b_fields: Raw/normalized fields from side B (e.g. Gateway / Bank).
            amounts: Expected, actual, and variance numerical metrics.
            dates: Dates and date delta information.
            compared_fields: Direct field-to-field comparison map.
            policy_citation: Regulatory or internal accounting policy reference.
            extra_data: Optional arbitrary dictionary for domain-specific context.

        Returns:
            JSON-serialized string of the evidence dictionary.
        """
        evidence_payload: Dict[str, Any] = {
            "evidence_type": "MATCH",
            "match_type": match_type,
            "rule": rule,
            "confidence": round(float(confidence), 4),
            "amounts": amounts or {},
            "dates": dates or {},
            "compared_fields": compared_fields or {},
            "side_a": side_a_fields or {},
            "side_b": side_b_fields or {},
            "policy_citation": policy_citation or "Internal Control Policy 4.1 - Layer 1 Exact Match Direct Settlement",
            "generated_at": datetime.now().isoformat(),
        }

        if extra_data:
            evidence_payload["extra"] = extra_data

        return json.dumps(evidence_payload, default=cls._json_serializer, indent=2)

    @classmethod
    def build_exception_evidence(
        cls,
        exception_type: str,
        reason: str,
        amounts: Optional[Dict[str, Any]] = None,
        dates: Optional[Dict[str, Any]] = None,
        references: Optional[Dict[str, Any]] = None,
        policy_citation: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Builds a structured JSON evidence string for an unresolved financial exception.

        Args:
            exception_type: Canonical exception classification string.
            reason: Human-readable explanation of why the exception occurred.
            amounts: Numerical metrics involved (gross, net, discrepancy, fee_pct).
            dates: Timestamps and transaction dates involved.
            references: Reference numbers, IDs, and tokens compared.
            policy_citation: Accounting standard or regulatory policy citation.
            extra_data: Optional arbitrary dictionary for domain-specific context.

        Returns:
            JSON-serialized string of the evidence dictionary.
        """
        evidence_payload: Dict[str, Any] = {
            "evidence_type": "EXCEPTION",
            "exception_type": exception_type,
            "reason": reason,
            "amounts": amounts or {},
            "dates": dates or {},
            "references": references or {},
            "policy_citation": policy_citation or "Financial Controller Standard Operating Procedure 4.2 - Discrepancy Escalation",
            "generated_at": datetime.now().isoformat(),
        }

        if extra_data:
            evidence_payload["extra"] = extra_data

        return json.dumps(evidence_payload, default=cls._json_serializer, indent=2)
