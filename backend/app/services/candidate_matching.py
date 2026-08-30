"""
Candidate Generation and Blocking Service.

Problem Solved:
Comparing every Bank transaction against every Gateway transaction and Invoice
in a naive Cartesian product is computationally expensive: O(N * M * K).
For batches of hundreds or thousands of transactions, this degrades throughput.

Why It Exists:
To prune the search space by identifying high-probability candidate pairs/triplets
using fast indexing on amount proximity, date settlement windows, and reference tokens.

Input:
Lists of normalized BankTransaction, GatewayTransaction, and Invoice entities.

Output:
Ranked candidate candidate match pairs/triplets ready for detailed scoring and AI verification.

Algorithm:
1. Exact & Proximity Amount Indexing (Hash bucket & tolerance search).
2. Date Window Filtering (+/- configurable tolerance days).
3. Core Reference Token Hash Table.
4. Candidate Pairing and Deduplication.
"""

from typing import List, Dict, Tuple, Optional, Any
from datetime import date, timedelta
from app.config import settings
from app.services.scoring import ScoringService
from app.services.normalization import NormalizationService


class CandidateMatchingService:
    """
    Generates high-probability candidate triplets/pairs across Bank, Gateway, and Invoices.
    """

    def __init__(
        self,
        amount_tolerance_pct: float = settings.AMOUNT_TOLERANCE_PCT,
        amount_tolerance_fixed: float = settings.AMOUNT_TOLERANCE_FIXED,
        date_tolerance_days: int = settings.DATE_TOLERANCE_DAYS,
    ):
        self.amount_tolerance_pct = amount_tolerance_pct
        self.amount_tolerance_fixed = amount_tolerance_fixed
        self.date_tolerance_days = date_tolerance_days
        self.scorer = ScoringService(date_max_tolerance_days=date_tolerance_days)

    def is_amount_compatible(self, a1: float, a2: float) -> bool:
        """Checks if two amounts are within acceptable proximity tolerance."""
        if a1 is None or a2 is None:
            return False
        diff = abs(a1 - a2)
        if diff < 0.01:
            return True
        max_val = max(abs(a1), abs(a2), 1.0)
        return (diff <= self.amount_tolerance_fixed) or (diff / max_val <= self.amount_tolerance_pct)

    def is_date_compatible(self, d1: date, d2: date) -> bool:
        """Checks if two dates fall within the settlement window."""
        if not d1 or not d2:
            return False
        return abs((d1 - d2).days) <= self.date_tolerance_days

    def generate_candidate_triplets(
        self,
        bank_records: List[Any],
        gateway_records: List[Any],
        invoice_records: List[Any],
    ) -> List[Dict[str, Any]]:
        """
        Generates 3-way candidate triplets (Bank, Gateway, Invoice) using multi-index blocking.
        Also surfaces 2-way partial candidates where one source is missing.
        """
        candidates = []
        matched_bank_ids = set()
        matched_gw_ids = set()
        matched_inv_ids = set()

        # Build reference lookup indices for instant O(1) matching
        gw_by_ref: Dict[str, List[Any]] = {}
        for gw in gateway_records:
            ref = getattr(gw, "normalized_ref", NormalizationService.normalize_reference(getattr(gw, "payment_reference", "")))
            if ref:
                gw_by_ref.setdefault(ref, []).append(gw)

        inv_by_ref: Dict[str, List[Any]] = {}
        for inv in invoice_records:
            ref = getattr(inv, "normalized_ref", NormalizationService.normalize_reference(getattr(inv, "invoice_reference", "")))
            if ref:
                inv_by_ref.setdefault(ref, []).append(inv)

        # -------------------------------------------------------------
        # Step 1: Direct Reference-Indexed Matching (Highest confidence)
        # -------------------------------------------------------------
        for bank in bank_records:
            b_ref = getattr(bank, "normalized_ref", NormalizationService.normalize_reference(getattr(bank, "reference", "")))
            b_amt = float(getattr(bank, "normalized_amount", getattr(bank, "amount", 0.0)))
            b_date = getattr(bank, "normalized_date", getattr(bank, "transaction_date", date.today()))
            b_desc = getattr(bank, "description", "")

            # Look up gateway transactions by ref
            potential_gws = gw_by_ref.get(b_ref, [])
            potential_invs = inv_by_ref.get(b_ref, [])

            # Check if any GW candidate matches amount/date
            best_gw = None
            best_gw_score = -1.0
            for gw in potential_gws:
                g_amt = float(getattr(gw, "normalized_amount", getattr(gw, "amount", 0.0)))
                g_net = float(getattr(gw, "net_settlement", 0.0) or 0.0)
                g_date = getattr(gw, "normalized_date", getattr(gw, "transaction_date", date.today()))
                
                amt_sim_gross = self.scorer.calculate_amount_similarity(b_amt, g_amt)
                amt_sim_net = self.scorer.calculate_amount_similarity(b_amt, g_net) if g_net > 0 else 0.0
                amt_sim = max(amt_sim_gross, amt_sim_net)
                
                date_sim = self.scorer.calculate_date_similarity(b_date, g_date)
                sim = (amt_sim * settings.BLOCKING_AMOUNT_WEIGHT) + (date_sim * settings.BLOCKING_DATE_WEIGHT)
                if sim > best_gw_score:
                    best_gw_score = sim
                    best_gw = gw

            # Check if any Invoice candidate matches amount/date
            best_inv = None
            best_inv_score = -1.0
            for inv in potential_invs:
                i_amt = float(getattr(inv, "normalized_amount", getattr(inv, "amount", 0.0)))
                i_date = getattr(inv, "normalized_date", getattr(inv, "invoice_date", date.today()))
                
                amt_sim = self.scorer.calculate_amount_similarity(b_amt, i_amt)
                date_sim = self.scorer.calculate_date_similarity(b_date, i_date)
                sim = (amt_sim * settings.BLOCKING_AMOUNT_WEIGHT) + (date_sim * settings.BLOCKING_DATE_WEIGHT)
                if sim > best_inv_score:
                    best_inv_score = sim
                    best_inv = inv

            if best_gw or best_inv:
                candidates.append({
                    "bank": bank,
                    "gateway": best_gw,
                    "invoice": best_inv,
                    "blocking_key": "reference_direct",
                })
                matched_bank_ids.add(getattr(bank, "bank_txn_id"))
                if best_gw:
                    matched_gw_ids.add(getattr(best_gw, "gateway_txn_id"))
                if best_inv:
                    matched_inv_ids.add(getattr(best_inv, "invoice_id"))

        # -------------------------------------------------------------
        # Step 2: Amount & Date Proximity Window Blocking for Unmatched Records
        # -------------------------------------------------------------
        remaining_banks = [b for b in bank_records if getattr(b, "bank_txn_id") not in matched_bank_ids]
        remaining_gws = [g for g in gateway_records if getattr(g, "gateway_txn_id") not in matched_gw_ids]
        remaining_invs = [i for i in invoice_records if getattr(i, "invoice_id") not in matched_inv_ids]

        for bank in remaining_banks:
            b_amt = float(getattr(bank, "normalized_amount", getattr(bank, "amount", 0.0)))
            b_date = getattr(bank, "normalized_date", getattr(bank, "transaction_date", date.today()))
            b_desc = getattr(bank, "description", "")
            b_ref = getattr(bank, "reference", "")

            best_gw = None
            best_gw_score = 0.0
            for gw in remaining_gws:
                g_amt = float(getattr(gw, "normalized_amount", getattr(gw, "amount", 0.0)))
                g_date = getattr(gw, "normalized_date", getattr(gw, "transaction_date", date.today()))
                g_cust = getattr(gw, "customer_name", "")
                g_ref = getattr(gw, "payment_reference", "")

                if self.is_amount_compatible(b_amt, g_amt) and self.is_date_compatible(b_date, g_date):
                    amt_sim = self.scorer.calculate_amount_similarity(b_amt, g_amt)
                    date_sim = self.scorer.calculate_date_similarity(b_date, g_date)
                    ref_sim = self.scorer.calculate_reference_similarity(b_ref, g_ref)
                    cust_sim = self.scorer.calculate_customer_similarity(b_desc, g_cust)
                    score_res = self.scorer.compute_match_score(amt_sim, date_sim, ref_sim, cust_sim)
                    if score_res["score"] > best_gw_score:
                        best_gw_score = score_res["score"]
                        best_gw = gw

            best_inv = None
            best_inv_score = 0.0
            for inv in remaining_invs:
                i_amt = float(getattr(inv, "normalized_amount", getattr(inv, "amount", 0.0)))
                i_date = getattr(inv, "normalized_date", getattr(inv, "invoice_date", date.today()))
                i_cust = getattr(inv, "customer_name", "")
                i_ref = getattr(inv, "invoice_reference", "")

                if self.is_amount_compatible(b_amt, i_amt) and self.is_date_compatible(b_date, i_date):
                    amt_sim = self.scorer.calculate_amount_similarity(b_amt, i_amt)
                    date_sim = self.scorer.calculate_date_similarity(b_date, i_date)
                    ref_sim = self.scorer.calculate_reference_similarity(b_ref, i_ref)
                    cust_sim = self.scorer.calculate_customer_similarity(b_desc, i_cust)
                    score_res = self.scorer.compute_match_score(amt_sim, date_sim, ref_sim, cust_sim)
                    if score_res["score"] > best_inv_score:
                        best_inv_score = score_res["score"]
                        best_inv = inv

            candidates.append({
                "bank": bank,
                "gateway": best_gw,
                "invoice": best_inv,
                "blocking_key": "proximity_window",
            })
            matched_bank_ids.add(getattr(bank, "bank_txn_id"))
            if best_gw:
                matched_gw_ids.add(getattr(best_gw, "gateway_txn_id"))
            if best_inv:
                matched_inv_ids.add(getattr(best_inv, "invoice_id"))

        # -------------------------------------------------------------
        # Step 3: Pair Remaining Gateway Records with Invoices
        # -------------------------------------------------------------
        unmatched_gws = [g for g in gateway_records if getattr(g, "gateway_txn_id") not in matched_gw_ids]
        unmatched_invs = [i for i in invoice_records if getattr(i, "invoice_id") not in matched_inv_ids]

        for gw in unmatched_gws:
            g_amt = float(getattr(gw, "normalized_amount", getattr(gw, "amount", 0.0)))
            g_date = getattr(gw, "normalized_date", getattr(gw, "transaction_date", date.today()))
            g_ref = getattr(gw, "payment_reference", "")
            g_cust = getattr(gw, "customer_name", "")

            best_inv = None
            best_score = 0.0
            for inv in unmatched_invs:
                i_amt = float(getattr(inv, "normalized_amount", getattr(inv, "amount", 0.0)))
                i_date = getattr(inv, "normalized_date", getattr(inv, "invoice_date", date.today()))
                i_ref = getattr(inv, "invoice_reference", "")
                i_cust = getattr(inv, "customer_name", "")

                if self.is_amount_compatible(g_amt, i_amt) and self.is_date_compatible(g_date, i_date):
                    amt_sim = self.scorer.calculate_amount_similarity(g_amt, i_amt)
                    date_sim = self.scorer.calculate_date_similarity(g_date, i_date)
                    ref_sim = self.scorer.calculate_reference_similarity(g_ref, i_ref)
                    cust_sim = self.scorer.calculate_customer_similarity(g_cust, i_cust)
                    score_res = self.scorer.compute_match_score(amt_sim, date_sim, ref_sim, cust_sim)
                    if score_res["score"] > best_score:
                        best_score = score_res["score"]
                        best_inv = inv

            candidates.append({
                "bank": None,
                "gateway": gw,
                "invoice": best_inv,
                "blocking_key": "gw_invoice_pair",
            })
            matched_gw_ids.add(getattr(gw, "gateway_txn_id"))
            if best_inv:
                matched_inv_ids.add(getattr(best_inv, "invoice_id"))

        # -------------------------------------------------------------
        # Step 4: Standalone Unmatched Invoices
        # -------------------------------------------------------------
        final_unmatched_invs = [i for i in invoice_records if getattr(i, "invoice_id") not in matched_inv_ids]
        for inv in final_unmatched_invs:
            candidates.append({
                "bank": None,
                "gateway": None,
                "invoice": inv,
                "blocking_key": "standalone_invoice",
            })

        return candidates
