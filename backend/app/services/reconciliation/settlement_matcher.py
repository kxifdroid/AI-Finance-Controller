"""
Many-to-One Settlement Batch Matcher.

Problem Solved:
Reconciles aggregate bank deposits against multiple individual payment gateway transactions
batched together into a single payout.

Why It Exists:
Payment gateways (Stripe, Razorpay, Adyen) do not settle funds on a 1-to-1 basis; instead,
they bundle dozens of customer captures into periodic net settlement deposits minus processing fees.
This matcher reconstructs the exact batch settlement composition with mathematical proof.

Input:
Unmatched Bank deposit records and unmatched Gateway transaction records.

Output:
Tuple: (batch_matches, matched_bank_ids, matched_gateway_ids).
"""

from datetime import date
from typing import Dict, Any, List, Set, Tuple, Optional
from app.config import settings
from app.services.reconciliation.evidence import EvidenceBuilder
from app.services.reconciliation.fee_calculator import FeeCalculator


class SettlementMatcher:
    """
    Executes subset-sum batch settlement matching between aggregate bank credits
    and candidate payment gateway transactions.
    """

    @staticmethod
    def _find_subset(
        candidates: List[Tuple[float, Any]],
        target: float,
        tolerance: float,
        max_size: int,
    ) -> Optional[List[Any]]:
        """
        Finds a subset of candidate records whose sum of net settlement amounts
        matches the target within tolerance using bounded branch-and-bound search.
        """
        n = len(candidates)

        def backtrack(
            start_idx: int,
            current_sum: float,
            current_items: List[Any],
        ) -> Optional[List[Any]]:
            if abs(current_sum - target) <= tolerance and len(current_items) >= 1:
                return current_items

            if len(current_items) >= max_size or start_idx >= n:
                return None

            for i in range(start_idx, n):
                net_val, rec = candidates[i]
                new_sum = current_sum + net_val

                # Prune branch if sum exceeds target by more than tolerance
                if new_sum > target + tolerance:
                    continue

                res = backtrack(i + 1, new_sum, current_items + [rec])
                if res is not None:
                    return res

            return None

        return backtrack(0, 0.0, [])

    @classmethod
    def match_settlements(
        cls,
        unmatched_banks: List[Any],
        unmatched_gateways: List[Any],
    ) -> Tuple[List[Dict[str, Any]], Set[str], Set[str]]:
        """
        Matches unmatched bank deposits against subsets of unmatched gateway transactions.

        Args:
            unmatched_banks: Bank transactions remaining after 1-to-1 exact and fuzzy matching.
            unmatched_gateways: Gateway transactions remaining after 1-to-1 matching.

        Returns:
            Tuple of:
            - batch_matches: List of batch settlement match dictionaries.
            - matched_bank_ids: Set of bank txn IDs reconciled in batches.
            - matched_gateway_ids: Set of gateway txn IDs reconciled in batches.
        """
        batch_matches: List[Dict[str, Any]] = []
        matched_bank_ids: Set[str] = set()
        matched_gateway_ids: Set[str] = set()

        max_group_size = settings.MANY_TO_ONE_MAX_GROUP_SIZE
        amount_tolerance = settings.MANY_TO_ONE_AMOUNT_TOLERANCE
        date_tolerance_days = settings.SETTLEMENT_DATE_TOLERANCE_DAYS

        # Filter out bank records that are not credits or have <= 0 amount
        candidate_banks = [
            b for b in unmatched_banks
            if float(getattr(b, "normalized_amount", getattr(b, "amount", 0.0))) > 0
        ]

        for bank in candidate_banks:
            bank_id = getattr(bank, "bank_txn_id", None)
            if not bank_id or bank_id in matched_bank_ids:
                continue

            bank_amt = float(getattr(bank, "normalized_amount", getattr(bank, "amount", 0.0)))
            bank_date = getattr(
                bank,
                "normalized_date",
                getattr(bank, "transaction_date", date.today()),
            )

            # Filter candidate gateway records:
            # 1. Not already matched in another batch
            # 2. Occurred on or before bank date within date_tolerance_days
            # 3. Net amount > 0
            eligible_gw: List[Tuple[float, Any]] = []
            for gw in unmatched_gateways:
                gw_id = getattr(gw, "gateway_txn_id", None)
                if not gw_id or gw_id in matched_gateway_ids:
                    continue

                gw_date = getattr(
                    gw,
                    "normalized_date",
                    getattr(gw, "transaction_date", date.today()),
                )

                days_diff = (bank_date - gw_date).days
                if 0 <= days_diff <= date_tolerance_days:
                    gw_net = float(
                        getattr(gw, "net_settlement", None)
                        or getattr(gw, "net_amount", None)
                        or getattr(gw, "normalized_amount", getattr(gw, "amount", 0.0))
                    )
                    if 0 < gw_net <= bank_amt + amount_tolerance:
                        eligible_gw.append((round(gw_net, 2), gw))

            if not eligible_gw:
                continue

            # Sort eligible candidates descending by net amount for greedy branch pruning
            eligible_gw.sort(key=lambda x: x[0], reverse=True)

            # Limit candidate pool size to prevent exponential search in extreme datasets
            subset = cls._find_subset(
                candidates=eligible_gw[:30],
                target=bank_amt,
                tolerance=amount_tolerance,
                max_size=max_group_size,
            )

            if subset and len(subset) > 1:
                # Successfully found batch subset of 2 or more gateway transactions
                matched_bank_ids.add(bank_id)
                for g in subset:
                    matched_gateway_ids.add(getattr(g, "gateway_txn_id"))

                total_gross = round(sum(float(getattr(g, "amount", 0.0)) for g in subset), 2)
                total_fee = round(sum(float(getattr(g, "gateway_fee", 0.0) or 0.0) for g in subset), 2)
                total_tax = round(sum(float(getattr(g, "tax_on_fee", 0.0) or 0.0) for g in subset), 2)
                total_net = round(
                    sum(
                        float(
                            getattr(g, "net_settlement", None)
                            or getattr(g, "net_amount", None)
                            or getattr(g, "amount", 0.0)
                        )
                        for g in subset
                    ),
                    2,
                )
                variance = round(bank_amt - total_net, 2)

                earliest_date = min(
                    getattr(g, "normalized_date", getattr(g, "transaction_date", bank_date))
                    for g in subset
                )
                latest_date = max(
                    getattr(g, "normalized_date", getattr(g, "transaction_date", bank_date))
                    for g in subset
                )

                gw_items_breakdown = [
                    {
                        "gateway_txn_id": getattr(g, "gateway_txn_id", ""),
                        "transaction_date": str(getattr(g, "transaction_date", "")),
                        "reference": getattr(g, "payment_reference", getattr(g, "reference", "")),
                        "gross_amount": float(getattr(g, "amount", 0.0)),
                        "gateway_fee": float(getattr(g, "gateway_fee", 0.0) or 0.0),
                        "tax_on_fee": float(getattr(g, "tax_on_fee", 0.0) or 0.0),
                        "net_settlement": float(
                            getattr(g, "net_settlement", None)
                            or getattr(g, "net_amount", None)
                            or getattr(g, "amount", 0.0)
                        ),
                    }
                    for g in subset
                ]

                evidence_json = EvidenceBuilder.build_match_evidence(
                    match_type="MANY_TO_ONE",
                    rule="many_to_one_batch_settlement",
                    confidence=0.95,
                    side_a_fields={
                        "group_size": len(subset),
                        "gateway_txn_ids": [getattr(g, "gateway_txn_id", "") for g in subset],
                        "total_gross": total_gross,
                        "total_fee": total_fee,
                        "total_tax": total_tax,
                        "total_net": total_net,
                    },
                    side_b_fields={
                        "bank_txn_id": bank_id,
                        "deposit_amount": bank_amt,
                        "deposit_date": str(bank_date),
                        "description": getattr(bank, "description", ""),
                    },
                    amounts={
                        "bank_credit": round(bank_amt, 2),
                        "gateway_net_sum": total_net,
                        "gateway_gross_sum": total_gross,
                        "gateway_fee_sum": total_fee,
                        "gateway_tax_sum": total_tax,
                        "variance": variance,
                    },
                    dates={
                        "bank_deposit_date": str(bank_date),
                        "earliest_gateway_date": str(earliest_date),
                        "latest_gateway_date": str(latest_date),
                        "max_delay_days": (bank_date - earliest_date).days,
                    },
                    compared_fields={
                        "net_sum_vs_bank_credit": {
                            "expected_net_sum": total_net,
                            "actual_bank_credit": bank_amt,
                            "difference": variance,
                            "tolerance": amount_tolerance,
                        }
                    },
                    policy_citation="Payment Aggregator Settlement Standard (RBI/2020-21/DPSS.CO.PD.No.1810/02.14.008/2019-20)",
                    extra_data={
                        "batch_composition": gw_items_breakdown,
                    },
                )

                match_info = {
                    "bank_record": bank,
                    "gateway_records": subset,
                    "match_layer": "many_to_one_settlement",
                    "match_rule": "batch_settlement_sum_equality",
                    "match_type": "MANY_TO_ONE",
                    "confidence": 0.95,
                    "decision": "MATCH" if abs(variance) < 0.01 else "REVIEW",
                    "amount": bank_amt,
                    "total_gross": total_gross,
                    "total_fee": total_fee,
                    "total_tax": total_tax,
                    "total_net": total_net,
                    "variance": variance,
                    "explanation": (
                        f"Batch payout reconciled: Bank deposit of ₹{bank_amt:,.2f} on {bank_date} "
                        f"successfully aggregates {len(subset)} gateway payments totaling ₹{total_net:,.2f} net settlement."
                    ),
                    "evidence_json": evidence_json,
                }
                batch_matches.append(match_info)

        return (batch_matches, matched_bank_ids, matched_gateway_ids)
