"""
Financial Accounting and Gateway Policy Service.

Problem Solved:
Maintains authoritative policy specifications, regulatory compliance standards,
and contractual fee schedules for payment gateways (Razorpay, Stripe), settlement clearing
windows, idempotency controls, and tax deduction thresholds.

Why It Exists:
To provide deterministic, auditable policy citations and mathematical parameter baselines
for the Exception Investigator Agent and reconciliation rule evaluation.

Input:
Exception type and transaction context dictionary.

Output:
Applicable policy metadata and list of regulatory/contractual citation strings.
"""

from typing import Dict, Any, List, Optional


# 1. Razorpay MDR Policy: Standard 2% MDR fee + 18% GST in India
RAZORPAY_MDR_POLICY: Dict[str, Any] = {
    "policy_id": "POL_RAZORPAY_MDR",
    "name": "Razorpay Merchant Discount Rate (MDR) & GST Policy",
    "citation": "Razorpay MDR Policy (2.0% MDR + 18% GST on fee = 2.36% effective deduction)",
    "description": (
        "Standard payment gateway fee structure in India comprising a 2.00% Merchant "
        "Discount Rate (MDR) plus 18.00% Goods and Services Tax (GST) applied on the processing "
        "fee, yielding an effective settlement deduction rate of 2.36%."
    ),
    "mdr_rate": 0.02,
    "gst_rate_on_fee": 0.18,
    "effective_deduction_rate": 0.0236,
    "tolerance_min_pct": 0.01,
    "tolerance_max_pct": 0.05,
    "applicable_exceptions": [
        "FEE_VARIANCE",
        "FEE_MISMATCH",
        "AMOUNT_MISMATCH",
        "PARTIAL_SETTLEMENT",
        "MANY_TO_ONE_SETTLEMENT",
    ],
}

# 2. Settlement Window Policy: T+1 to T+3 clearing window
SETTLEMENT_WINDOW_POLICY: Dict[str, Any] = {
    "policy_id": "POL_SETTLEMENT_WINDOW",
    "name": "Settlement Clearing Window Policy",
    "citation": "RBI Payment Aggregator Settlement Guidelines (T+1 to T+3 Clearing Window)",
    "description": (
        "Regulatory settlement timeline for payment aggregators and nodal bank accounts. "
        "Captured customer payments must be settled to merchant bank accounts within "
        "T+1 to T+3 business days, excluding declared banking holidays."
    ),
    "min_days": 1,
    "max_days": 3,
    "weekend_tolerance_days": 2,
    "applicable_exceptions": [
        "TIMING_DIFFERENCE",
        "DATE_MISMATCH",
        "MISSING_BANK_SETTLEMENT",
        "MANY_TO_ONE_SETTLEMENT",
    ],
}

# 3. Idempotency Policy: Duplicate capture prevention
IDEMPOTENCY_POLICY: Dict[str, Any] = {
    "policy_id": "POL_IDEMPOTENCY",
    "name": "Duplicate Capture Prevention & Idempotency Key Standard",
    "citation": "Anti-Double-Billing Compliance Framework & Gateway Idempotency Standard RFC 7231",
    "description": (
        "Strict duplicate capture prevention standard enforcing unique idempotency keys "
        "across payment capture endpoints. Multiple captures with identical monetary "
        "amount, customer identity, and payment reference within a 90-second or same-day "
        "window must be flagged for immediate gateway voiding/refund."
    ),
    "collision_window_seconds": 90,
    "applicable_exceptions": [
        "DUPLICATE_TRANSACTION",
        "DUPLICATE",
    ],
}

# 4. TDS Section 194H Policy: Section 194H TDS on commission
TDS_194H_POLICY: Dict[str, Any] = {
    "policy_id": "POL_TDS_194H",
    "name": "Section 194H TDS on Gateway Commission/Brokerage",
    "citation": "Income Tax Act Section 194H - TDS on Commission / Gateway Brokerage (5% TDS on fee charges)",
    "description": (
        "Statutory withholding tax compliance under Section 194H of the Indian Income Tax Act. "
        "Applicable at 5% on gateway processing commission and brokerage charges when aggregate "
        "annual gateway fee deductions exceed the ₹15,000 threshold."
    ),
    "tds_rate": 0.05,
    "annual_exemption_threshold": 15000.0,
    "applicable_exceptions": [
        "TAX_MISMATCH",
        "FEE_MISMATCH",
        "FEE_VARIANCE",
    ],
}

# 5. Materiality Policy: ₹5,000 auto-clear ceiling
MATERIALITY_POLICY: Dict[str, Any] = {
    "policy_id": "POL_MATERIALITY",
    "name": "Materiality Ceiling & Auto-Clear Threshold Policy",
    "citation": "Internal Financial Controller Standard Operating Procedure 4.2 - Materiality Ceiling (₹5,000 Threshold)",
    "description": (
        "Internal treasury control threshold governing autonomous variance resolution. "
        "Discrepancies below the ₹5,000 ceiling can be auto-cleared if supported by deterministic "
        "formulaic proof (e.g. MDR fee math); discrepancies equal to or exceeding ₹5,000 require "
        "mandatory human operator sign-off and high-severity escalation."
    ),
    "auto_clear_ceiling": 5000.0,
    "applicable_exceptions": [
        "AMOUNT_MISMATCH",
        "FEE_VARIANCE",
        "FEE_MISMATCH",
        "PARTIAL_SETTLEMENT",
        "NO_MATCH_FOUND",
        "MISSING_ERP_TRANSACTION",
        "MISSING_GATEWAY_TRANSACTION",
        "MISSING_BANK_SETTLEMENT",
        "TIMING_DIFFERENCE",
        "DATE_MISMATCH",
        "MANY_TO_ONE_SETTLEMENT",
        "UNKNOWN",
    ],
}

# Master registry of all policies
ALL_POLICIES: Dict[str, Dict[str, Any]] = {
    "RAZORPAY_MDR_POLICY": RAZORPAY_MDR_POLICY,
    "SETTLEMENT_WINDOW_POLICY": SETTLEMENT_WINDOW_POLICY,
    "IDEMPOTENCY_POLICY": IDEMPOTENCY_POLICY,
    "TDS_194H_POLICY": TDS_194H_POLICY,
    "MATERIALITY_POLICY": MATERIALITY_POLICY,
}


class PolicyService:
    """
    Centralized repository and evaluator for financial accounting and payment gateway policies.
    """

    RAZORPAY_MDR_POLICY = RAZORPAY_MDR_POLICY
    SETTLEMENT_WINDOW_POLICY = SETTLEMENT_WINDOW_POLICY
    IDEMPOTENCY_POLICY = IDEMPOTENCY_POLICY
    TDS_194H_POLICY = TDS_194H_POLICY
    MATERIALITY_POLICY = MATERIALITY_POLICY

    @classmethod
    def get_applicable_policies(
        cls,
        exception_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Evaluates exception classification and monetary context to return
        an ordered list of applicable policy citations.

        Args:
            exception_type: Canonical exception classification string
                            (e.g., 'FEE_VARIANCE', 'TIMING_DIFFERENCE', 'DUPLICATE_TRANSACTION').
            context: Optional dictionary containing context values such as:
                     - 'amount': float
                     - 'discrepancy': float
                     - 'fee_amount': float
                     - 'days_diff': int

        Returns:
            List of unique policy citation strings.
        """
        citations: List[str] = []
        exc_upper = str(exception_type or "").upper().strip()
        ctx = context or {}

        # 1. Fee / MDR / Tax related
        if any(k in exc_upper for k in ("FEE", "MDR", "COMMISSION")):
            citations.append(RAZORPAY_MDR_POLICY["citation"])
            fee_amt = ctx.get("fee_amount", ctx.get("discrepancy", 0.0))
            if fee_amt and float(fee_amt) > 1000.0:
                citations.append(TDS_194H_POLICY["citation"])
            citations.append(MATERIALITY_POLICY["citation"])

        elif "TAX" in exc_upper:
            citations.append(TDS_194H_POLICY["citation"])
            citations.append(RAZORPAY_MDR_POLICY["citation"])
            citations.append(MATERIALITY_POLICY["citation"])

        # 2. Timing / Settlement Window related
        elif any(k in exc_upper for k in ("TIMING", "DATE", "MISSING_BANK", "LAG")):
            citations.append(SETTLEMENT_WINDOW_POLICY["citation"])
            citations.append(MATERIALITY_POLICY["citation"])

        # 3. Duplicate Transaction related
        elif "DUPLICATE" in exc_upper:
            citations.append(IDEMPOTENCY_POLICY["citation"])
            citations.append(MATERIALITY_POLICY["citation"])

        # 4. Many-to-One Batch Settlement related
        elif "MANY_TO_ONE" in exc_upper or "BATCH" in exc_upper:
            citations.append(SETTLEMENT_WINDOW_POLICY["citation"])
            citations.append(RAZORPAY_MDR_POLICY["citation"])
            citations.append(MATERIALITY_POLICY["citation"])

        # 5. Amount Mismatch / Partial Settlement related
        elif any(k in exc_upper for k in ("AMOUNT", "PARTIAL", "MISMATCH")):
            amt = ctx.get("amount", 0.0)
            disc = ctx.get("discrepancy", 0.0)
            # Check if discrepancy matches standard ~2.36% fee
            if amt and disc and (0.01 <= (float(disc) / float(amt)) <= 0.05):
                citations.append(RAZORPAY_MDR_POLICY["citation"])
            citations.append(MATERIALITY_POLICY["citation"])

        # 6. Default fallback
        else:
            citations.append(MATERIALITY_POLICY["citation"])

        # Deduplicate citations while preserving order
        seen = set()
        unique_citations = []
        for cit in citations:
            if cit not in seen:
                seen.add(cit)
                unique_citations.append(cit)

        return unique_citations

    @classmethod
    def get_policy(cls, policy_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a specific policy specification dictionary by name."""
        return ALL_POLICIES.get(policy_name)

    @classmethod
    def get_all_policies(cls) -> Dict[str, Dict[str, Any]]:
        """Returns all registered policy specifications."""
        return dict(ALL_POLICIES)
