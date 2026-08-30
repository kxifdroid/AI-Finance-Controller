"""
Deterministic Scoring Service for Financial Reconciliation.

Problem Solved:
Calculates transparent, interpretable mathematical similarity scores between
candidate transactions across amount, date, reference, and customer dimensions.

Why It Exists:
To provide deterministic, reproducible confidence metrics without relying
blindly on stochastic LLMs for basic mathematical comparisons.

Input:
Pairs or triplets of normalized financial records (Bank, Gateway, Invoice).

Output:
Composite score [0.0 - 1.0], individual component similarity features, and a structured explanation.

Algorithm:
- Amount Similarity: Exact match = 1.0; exponential/relative decay for fee variations.
- Date Similarity: Day delta distance decay within tolerance window.
- Reference Similarity: RapidFuzz token matching + exact core alphanumeric containment.
- Customer Similarity: RapidFuzz token_set_ratio on normalized entity strings.
- Weighted Linear Combination: Configurable weights summing to 1.0.
"""

from datetime import date
from typing import Dict, Any, Optional
import math
from rapidfuzz import fuzz
from app.config import settings
from app.services.normalization import NormalizationService


class ScoringService:
    """
    Computes multi-factor similarity metrics between financial transaction records.
    """

    def __init__(
        self,
        weight_amount: float = settings.WEIGHT_AMOUNT,
        weight_reference: float = settings.WEIGHT_REFERENCE,
        weight_date: float = settings.WEIGHT_DATE,
        weight_customer: float = settings.WEIGHT_CUSTOMER,
        date_max_tolerance_days: int = settings.DATE_TOLERANCE_DAYS,
    ):
        # Normalize weights so they sum to 1.0
        total_w = weight_amount + weight_reference + weight_date + weight_customer
        self.w_amount = weight_amount / total_w
        self.w_reference = weight_reference / total_w
        self.w_date = weight_date / total_w
        self.w_customer = weight_customer / total_w
        self.date_max_tolerance_days = max(1, date_max_tolerance_days)

    def calculate_amount_similarity(self, amount1: float, amount2: float, allow_fee_variance: bool = False) -> float:
        """
        Calculates similarity between two monetary amounts.
        Exact match (diff < 0.01) = 1.0.
        Any variance decays exponentially based on relative difference unless explicit fee variance is allowed.
        """
        if amount1 is None or amount2 is None:
            return 0.0
        
        a1, a2 = float(amount1), float(amount2)
        diff = abs(a1 - a2)
        
        # Exact match
        if diff < 0.01:
            return 1.0
        
        max_val = max(abs(a1), abs(a2), 1.0)
        pct_diff = diff / max_val
        
        # Only allow 1.0 if explicit fee variance check is enabled
        if allow_fee_variance and pct_diff <= settings.FEE_VARIANCE_MAX_PCT:
            return 1.0
        
        # Exponential decay: e^(-10.0 * pct_diff)
        # e.g., 5% diff -> e^(-0.5) = 0.6065; 10% diff -> e^(-1.0) = 0.3679
        score = math.exp(-settings.SCORING_AMOUNT_DECAY_RATE * pct_diff)
        return round(max(0.0, score), 4)

    def calculate_3way_amount_similarity(
        self,
        invoice_amount: Optional[float],
        gateway_gross: Optional[float],
        gateway_fee: Optional[float],
        gateway_tax: Optional[float],
        bank_credit: Optional[float],
    ) -> float:
        """
        Evaluates amount similarity across the entire 3-way lifecycle:
        Leg 1: Invoice Amount vs Gateway Gross
        Leg 2: Expected Net Settlement (Gross - Fee - Tax) vs Bank Credit
        Returns minimum similarity across both legs.
        """
        inv_amt = float(invoice_amount) if invoice_amount is not None else None
        gw_amt = float(gateway_gross) if gateway_gross is not None else None
        fee = float(gateway_fee or 0.0)
        tax = float(gateway_tax or 0.0)
        bank_amt = float(bank_credit) if bank_credit is not None else None

        # Leg 1: Invoice vs Gateway Gross
        if inv_amt is not None and gw_amt is not None:
            sim1 = self.calculate_amount_similarity(inv_amt, gw_amt)
        else:
            sim1 = 1.0 if (inv_amt is None and gw_amt is None) else 0.0

        # Leg 2: Gateway Net vs Bank Credit
        if gw_amt is not None and bank_amt is not None:
            expected_net = gw_amt - fee - tax if fee > 0 else gw_amt
            sim2 = self.calculate_amount_similarity(expected_net, bank_amt)
        elif inv_amt is not None and bank_amt is not None:
            sim2 = self.calculate_amount_similarity(inv_amt, bank_amt)
        else:
            sim2 = 1.0 if (gw_amt is None and bank_amt is None) else 0.0

        return round(min(sim1, sim2), 4)

    def calculate_date_similarity(self, date1: date, date2: date) -> float:
        """
        Calculates similarity between two transaction dates using configured step weights.
        """
        if not date1 or not date2:
            return 0.0
        
        delta_days = abs((date1 - date2).days)
        step_weights = settings.SCORING_DATE_STEP_WEIGHTS  # default [0.95, 0.90, 0.35]
        
        if delta_days == 0:
            return 1.0
        elif delta_days == 1 and len(step_weights) > 0:
            return step_weights[0]
        elif delta_days == 2 and len(step_weights) > 1:
            return step_weights[1]
        
        if delta_days > self.date_max_tolerance_days:
            # Minor residual if within 2x tolerance, else 0
            if delta_days <= self.date_max_tolerance_days * 2:
                return round(max(0.0, 0.5 * (1.0 - (delta_days - self.date_max_tolerance_days) / self.date_max_tolerance_days)), 4)
            return 0.0
        
        decay_factor = step_weights[2] if len(step_weights) > 2 else 0.35
        score = 1.0 - (delta_days / (self.date_max_tolerance_days + 1)) * decay_factor
        return round(max(0.0, score), 4)

    def calculate_reference_similarity(self, ref1: str, ref2: str) -> float:
        """
        Calculates similarity between two reference/invoice identifiers.
        Handles formatting differences (e.g. 'REF-83921' vs '83921' or 'PG_83921').
        """
        if not ref1 or not ref2:
            return 0.0
        
        norm1 = NormalizationService.normalize_reference(ref1)
        norm2 = NormalizationService.normalize_reference(ref2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Exact match of normalized core
        if norm1 == norm2:
            return 1.0
        
        # Substring containment (e.g. core ID embedded in a longer composite code)
        if norm1 in norm2 or norm2 in norm1:
            min_len = min(len(norm1), len(norm2))
            if min_len >= 4:
                return 0.95
        
        # Fuzzy token sort ratio
        ratio = fuzz.token_sort_ratio(norm1, norm2) / 100.0
        partial = fuzz.partial_ratio(norm1, norm2) / 100.0
        
        best = max(ratio, partial * 0.9)
        return round(best, 4)

    def calculate_customer_similarity(self, name1: str, name2: str) -> float:
        """
        Calculates similarity between two customer/counterparty names using fuzzy token sets.
        """
        if not name1 or not name2:
            return 0.0
        
        norm1 = NormalizationService.normalize_customer_name(name1)
        norm2 = NormalizationService.normalize_customer_name(name2)
        
        if not norm1 or not norm2:
            return 0.0
        
        if norm1 == norm2:
            return 1.0
        
        # Token set ratio is resilient to word ordering and partial sub-names
        token_set = fuzz.token_set_ratio(norm1, norm2) / 100.0
        token_sort = fuzz.token_sort_ratio(norm1, norm2) / 100.0
        
        score = (token_set * 0.7) + (token_sort * 0.3)
        return round(score, 4)

    def calculate_description_similarity(self, description: str, counterparty: str, reference: str) -> float:
        """
        Checks if counterparty or reference token exists within bank statement description text.
        """
        if not description:
            return 0.0
        
        norm_desc = NormalizationService.normalize_description(description)
        norm_ref = NormalizationService.normalize_reference(reference)
        norm_cust = NormalizationService.normalize_customer_name(counterparty)
        
        ref_hit = 1.0 if norm_ref and norm_ref in norm_desc else 0.0
        cust_hit = 1.0 if norm_cust and norm_cust in norm_desc else (fuzz.partial_ratio(norm_cust, norm_desc) / 100.0 if norm_cust else 0.0)
        
        return round(max(ref_hit, cust_hit), 4)

    def compute_match_score(
        self,
        amount_sim: float,
        date_sim: float,
        reference_sim: float,
        customer_sim: float,
    ) -> Dict[str, Any]:
        """
        Computes composite weighted matching score and generates explanatory factors.
        """
        composite = (
            (self.w_amount * amount_sim)
            + (self.w_reference * reference_sim)
            + (self.w_date * date_sim)
            + (self.w_customer * customer_sim)
        )
        composite = round(min(1.0, max(0.0, composite)), 4)

        factors = []
        if amount_sim >= 0.99:
            factors.append("Exact monetary amount match")
        elif amount_sim >= 0.70:
            factors.append(f"Minor amount discrepancy ({round((1 - amount_sim) * 100, 1)}% variance)")
        else:
            factors.append("Significant amount discrepancy")

        if reference_sim >= 0.95:
            factors.append("Direct reference/identifier match")
        elif reference_sim >= 0.70:
            factors.append("Partial reference overlap")

        if date_sim >= 0.95:
            factors.append("Dates coincide within 1 day")
        elif date_sim >= 0.70:
            factors.append("Dates within allowable settlement window")

        if customer_sim >= 0.90:
            factors.append("Counterparty names match after entity normalization")

        explanation = ". ".join(factors) + "."

        return {
            "score": composite,
            "features": {
                "amount_similarity": round(amount_sim, 4),
                "date_similarity": round(date_sim, 4),
                "reference_similarity": round(reference_sim, 4),
                "customer_similarity": round(customer_sim, 4),
            },
            "explanation": explanation,
        }
