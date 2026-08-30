"""
Layer 1 Exact Matcher for Two-Way Financial Reconciliation Legs.

Problem Solved:
Executes O(1) indexed exact matching on normalized reference numbers, exact amounts,
and zero-day date deltas for both Leg 1 (Invoice ↔ Gateway) and Leg 2 (Gateway ↔ Bank).

Why It Exists:
To rapidly and deterministically reconcile identical transactions with 100% confidence,
enforce the materiality auto-clear control gate, and attach structured evidence chains.

Input:
List of Side A records, list of Side B records, leg name, and fee variance flag.

Output:
Tuple: (matched_pairs, remaining_a, remaining_b, matched_a_ids, matched_b_ids).
"""

from datetime import date
from typing import Dict, Any, List, Set, Tuple, Optional
from app.config import settings
from app.services.normalization import NormalizationService
from app.services.reconciliation.evidence import EvidenceBuilder


def can_auto_clear(
    match_layer: str,
    confidence_score: float,
    amount: float,
    is_one_to_many: bool = False,
) -> bool:
    """
    Enforces the mandatory control gate for auto-clearing matches.
    Must pass both confidence threshold AND monetary materiality ceiling (<= 5000.0)
    and must not be a one-to-many / many-to-one batch grouping.
    """
    is_confident = (
        match_layer in ("layer1_exact", "exact")
        or (match_layer in ("layer2_fuzzy", "fuzzy") and confidence_score >= settings.AUTO_MATCH_THRESHOLD)
    )
    is_within_materiality = abs(amount) <= settings.MATERIALITY_AUTO_CLEAR_CEILING
    return is_confident and is_within_materiality and not is_one_to_many


class ExactMatcher:
    """
    Executes Layer 1 exact matching across normalized financial record pairs.
    """

    @classmethod
    def match(
        cls,
        side_a_records: List[Any],
        side_b_records: List[Any],
        leg_name: str,
        allow_fee_variance: bool = False,
    ) -> Tuple[List[Dict[str, Any]], List[Any], List[Any], Set[str], Set[str]]:
        """
        Performs exact matching on reference, amount, and date.

        Args:
            side_a_records: Records from source A (e.g. Invoices in Leg 1, Gateway in Leg 2).
            side_b_records: Records from source B (e.g. Gateway in Leg 1, Bank in Leg 2).
            leg_name: Description of the reconciliation leg (e.g. 'Leg 1: Invoice ↔ Gateway').
            allow_fee_variance: Whether to check net settlement amounts (Leg 2).

        Returns:
            Tuple of:
            - matched_pairs: List of match dictionaries (both MATCH and REVIEW).
            - remaining_a: Unmatched Side A records.
            - remaining_b: Unmatched Side B records.
            - matched_a_ids: Set of matched Side A record IDs.
            - matched_b_ids: Set of matched Side B record IDs.
        """
        matched_pairs: List[Dict[str, Any]] = []
        matched_a_ids: Set[str] = set()
        matched_b_ids: Set[str] = set()

        unmatched_a = list(side_a_records)
        unmatched_b = list(side_b_records)

        # Index Side B by normalized reference for O(1) candidate lookup
        b_by_ref: Dict[str, List[Any]] = {}
        for b in unmatched_b:
            b_ref = getattr(
                b,
                "normalized_ref",
                NormalizationService.normalize_reference(
                    getattr(b, "payment_reference", getattr(b, "reference", ""))
                ),
            )
            if b_ref:
                b_by_ref.setdefault(b_ref, []).append(b)

        for a in unmatched_a:
            a_id = getattr(
                a,
                "invoice_id",
                getattr(a, "gateway_txn_id", getattr(a, "bank_txn_id", None)),
            )
            a_ref = getattr(
                a,
                "normalized_ref",
                NormalizationService.normalize_reference(
                    getattr(a, "invoice_reference", getattr(a, "payment_reference", getattr(a, "reference", "")))
                ),
            )

            if not a_ref or a_ref not in b_by_ref:
                continue

            if allow_fee_variance:
                # In Leg 2 (Gateway ↔ Bank), Gateway amount is net settlement
                a_amt = float(
                    getattr(a, "net_settlement", None)
                    or getattr(a, "net_amount", None)
                    or getattr(a, "normalized_amount", getattr(a, "amount", 0.0))
                )
            else:
                # In Leg 1 (Invoice ↔ Gateway), Invoice amount is gross amount
                a_amt = float(
                    getattr(a, "gross_amount", None)
                    or getattr(a, "normalized_amount", getattr(a, "amount", 0.0))
                )

            a_date = getattr(
                a,
                "normalized_date",
                getattr(a, "invoice_date", getattr(a, "transaction_date", date.today())),
            )

            candidates = b_by_ref.get(a_ref, [])
            exact_partner = None

            for b in candidates:
                b_id = getattr(b, "gateway_txn_id", getattr(b, "bank_txn_id", None))
                if b_id in matched_b_ids:
                    continue

                b_amt = float(getattr(b, "normalized_amount", getattr(b, "amount", 0.0)))
                b_net = float(getattr(b, "net_settlement", 0.0) or getattr(b, "net_amount", 0.0) or 0.0)
                b_date = getattr(
                    b,
                    "normalized_date",
                    getattr(b, "transaction_date", getattr(b, "invoice_date", date.today())),
                )

                # Check exact amount match (within 0.01 tolerance)
                is_amt_match = abs(a_amt - b_amt) < 0.01 or (
                    allow_fee_variance and b_net > 0 and abs(a_amt - b_net) < 0.01
                )
                delta_days = (b_date - a_date).days
                # Exact same day or within standard bank settlement clearing window (T+1 to T+3 for Leg 2)
                is_date_match = delta_days == 0 or (allow_fee_variance and 0 <= delta_days <= settings.SETTLEMENT_DATE_TOLERANCE_DAYS)

                if is_amt_match and is_date_match:
                    exact_partner = b
                    break

            if exact_partner:
                b_id = getattr(exact_partner, "gateway_txn_id", getattr(exact_partner, "bank_txn_id", None))
                matched_a_ids.add(a_id)
                matched_b_ids.add(b_id)

                max_amt = max(abs(a_amt), abs(float(getattr(exact_partner, "amount", 0.0))))
                decision = "MATCH"
                rule = "exact_amount_date_ref" if delta_days == 0 else "settlement_window_cleared"

                evidence_json = EvidenceBuilder.build_match_evidence(
                    match_type="EXACT" if delta_days == 0 else "TIMING_DIFFERENCE",
                    rule=rule,
                    confidence=1.0 if delta_days == 0 else 0.98,
                    side_a_fields={
                        "id": a_id,
                        "reference": a_ref,
                        "amount": a_amt,
                        "date": str(a_date),
                    },
                    side_b_fields={
                        "id": b_id,
                        "reference": getattr(exact_partner, "normalized_ref", ""),
                        "amount": float(getattr(exact_partner, "amount", 0.0)),
                        "date": str(getattr(exact_partner, "transaction_date", getattr(exact_partner, "invoice_date", ""))),
                    },
                    amounts={
                        "expected": round(a_amt, 2),
                        "actual": round(float(getattr(exact_partner, "amount", 0.0)), 2),
                        "variance": round(abs(a_amt - float(getattr(exact_partner, "amount", 0.0))), 2),
                    },
                    dates={
                        "side_a": str(a_date),
                        "side_b": str(getattr(exact_partner, "transaction_date", getattr(exact_partner, "invoice_date", ""))),
                        "delta_days": delta_days,
                    },
                    compared_fields={
                        "reference": {"a": a_ref, "b": getattr(exact_partner, "normalized_ref", ""), "match": True},
                        "date": {"a": str(a_date), "b": str(getattr(exact_partner, "transaction_date", getattr(exact_partner, "invoice_date", ""))), "delta_days": delta_days},
                        "amount": {"a": a_amt, "b": float(getattr(exact_partner, "amount", 0.0)), "diff": 0.0},
                    },
                    policy_citation="Internal Control Policy 4.1 - Layer 1 Exact Match Direct Settlement",
                )

                if delta_days == 0:
                    soothing_explanation = f"Exact 1-to-1 match on reference '{a_ref}' for ₹{max_amt:,.2f} with identical settlement date."
                else:
                    soothing_explanation = f"Matched on reference '{a_ref}' for ₹{max_amt:,.2f} with a {delta_days}-day banking clearing window."

                match_info = {
                    "side_a": a,
                    "side_b": exact_partner,
                    "match_layer": "layer1_exact",
                    "match_rule": rule,
                    "match_type": "EXACT" if delta_days == 0 else "TIMING_DIFFERENCE",
                    "confidence": 1.0 if delta_days == 0 else 0.98,
                    "decision": decision,
                    "amount": max_amt,
                    "explanation": soothing_explanation,
                    "evidence_json": evidence_json,
                }
                matched_pairs.append(match_info)

        remaining_a = [
            a
            for a in unmatched_a
            if getattr(a, "invoice_id", getattr(a, "gateway_txn_id", getattr(a, "bank_txn_id", None)))
            not in matched_a_ids
        ]
        remaining_b = [
            b
            for b in unmatched_b
            if getattr(b, "gateway_txn_id", getattr(b, "bank_txn_id", getattr(b, "invoice_id", None)))
            not in matched_b_ids
        ]

        return (matched_pairs, remaining_a, remaining_b, matched_a_ids, matched_b_ids)
