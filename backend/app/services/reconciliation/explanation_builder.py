"""
Deterministic Explanation Builder for Financial Reconciliation.
Generates unambiguous, factual, and strictly non-contradictory human-readable explanations
derived solely from canonical reason codes and exact mathematical evidence deltas.
"""

from typing import Dict, Any, Optional
from app.services.reconciliation.canonical_codes import CanonicalReasonCode


class ExplanationBuilder:
    """
    Constructs factual auditor explanations and actionable recommendations based on canonical reason codes.
    Guarantees that non-matched statuses (REVIEW, EXCEPTION, DUPLICATE, MISSING) never receive positive match phrasing.
    """

    @classmethod
    def build_explanation_and_action(
        cls,
        decision: str,
        reason_code: str,
        amounts: Dict[str, float],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Builds the deterministic explanation and recommended action.

        Args:
            decision: MATCH, REVIEW, EXCEPTION, DUPLICATE, MISSING
            reason_code: CanonicalReasonCode string
            amounts: Dictionary containing invoice_total, gateway_gross_total, gateway_net_total, bank_credit_total, variance, fee_total, tax_total
            context: Additional metadata (e.g. reference, customer, delta_days, dates, counts)

        Returns:
            Dict with 'explanation' and 'recommended_action'
        """
        ctx = context or {}
        ref = ctx.get("reference", "N/A")
        cust = ctx.get("customer", "Customer")
        delta_days = ctx.get("delta_days", 0)
        gw_count = ctx.get("gateway_count", 1)

        inv_amt = float(amounts.get("invoice_total", 0.0) or 0.0)
        gw_gross = float(amounts.get("gateway_gross_total", 0.0) or 0.0)
        gw_net = float(amounts.get("gateway_net_total", 0.0) or 0.0)
        bank_credit = float(amounts.get("bank_credit_total", 0.0) or 0.0)
        fee = float(amounts.get("fee_total", 0.0) or 0.0)
        tax = float(amounts.get("tax_total", 0.0) or 0.0)
        variance = float(amounts.get("variance", 0.0) or 0.0)

        # -------------------------------------------------------------
        # 1. Deterministic MATCH Explanations
        # -------------------------------------------------------------
        if decision == "MATCH":
            if reason_code == CanonicalReasonCode.EXACT_3_WAY_MATCH:
                exp = (
                    f"Fully reconciled across ERP Invoice, Payment Gateway, and Bank Statement. "
                    f"Reference '{ref}', exact amount (₹{gw_gross:,.2f}), and same-day settlement match identically."
                )
                action = "No action required. Transaction verified and reconciled."

            elif reason_code == CanonicalReasonCode.FEE_RECONCILED:
                fee_pct_str = f"{(fee / gw_gross * 100):.2f}%" if gw_gross > 0 else "standard"
                exp = (
                    f"Reconciled with standard payment gateway MDR fee deduction ({fee_pct_str} fee + 18% GST). "
                    f"Invoiced ₹{inv_amt:,.2f} gross; Bank received ₹{bank_credit:,.2f} net settlement with zero unexplained variance."
                )
                action = "No action required. Fee and tax deductions conform to standard gateway fee schedule."

            elif reason_code == CanonicalReasonCode.TIMING_DIFFERENCE:
                exp = (
                    f"Reconciled across all systems with a {delta_days}-day banking clearing window "
                    f"(captured {ctx.get('gateway_date', '')}, credited {ctx.get('bank_date', '')}). "
                    f"Reference '{ref}' and amount (₹{gw_gross:,.2f}) match verified."
                )
                action = f"Settlement verified within permissible T+{delta_days} bank clearing window."

            elif reason_code == CanonicalReasonCode.MANY_TO_ONE_MATCH:
                exp = (
                    f"Batch payout reconciled: Bank deposit of ₹{bank_credit:,.2f} "
                    f"successfully aggregates {gw_count} gateway captures totaling ₹{gw_gross:,.2f} with zero variance."
                )
                action = "Batch deposit verified against aggregate gateway captures."

            else:
                exp = f"Transaction reconciled successfully on reference '{ref}' for ₹{gw_gross:,.2f}."
                action = "Reconciliation complete. Verified."

            return {"explanation": exp, "recommended_action": action}

        # -------------------------------------------------------------
        # 2. REVIEW & EXCEPTION Explanations (Strictly Non-Positive)
        # -------------------------------------------------------------
        if reason_code == CanonicalReasonCode.AMOUNT_MISMATCH:
            if inv_amt > 0 and gw_gross > 0 and abs(inv_amt - gw_gross) < 0.01 and bank_credit > 0 and abs(gw_gross - bank_credit) >= 0.01:
                amt_diff = abs(gw_gross - bank_credit)
                exp = (
                    f"Amount mismatch: ERP Invoice and Payment Gateway both show ₹{inv_amt:,.2f}, "
                    f"but Bank credit received is ₹{bank_credit:,.2f}, resulting in an unexplained ₹{amt_diff:,.2f} variance."
                )
                action = f"Investigate bank credit variance of ₹{amt_diff:,.2f} with payment gateway provider."
            elif inv_amt > 0 and gw_gross > 0 and inv_amt > gw_gross:
                underpay = abs(inv_amt - gw_gross)
                exp = (
                    f"Underpayment detected: ERP Invoice billed ₹{inv_amt:,.2f}, but Gateway captured only ₹{gw_gross:,.2f} "
                    f"(short by ₹{underpay:,.2f})."
                )
                action = f"Follow up with {cust} for remaining ₹{underpay:,.2f} balance or issue credit adjustment."
            elif inv_amt > 0 and gw_gross > 0 and gw_gross > inv_amt:
                overpay = abs(gw_gross - inv_amt)
                exp = (
                    f"Overpayment detected: ERP Invoice billed ₹{inv_amt:,.2f}, but Gateway captured ₹{gw_gross:,.2f} "
                    f"(overpaid by ₹{overpay:,.2f})."
                )
                action = f"Review overpayment of ₹{overpay:,.2f} and issue customer credit balance."
            else:
                exp = (
                    f"Amount mismatch detected across records. Expected ₹{max(inv_amt, gw_gross):,.2f}, "
                    f"settled ₹{bank_credit:,.2f} (variance delta: ₹{abs(variance):,.2f})."
                )
                action = "Review ledger settlement breakdown to identify source of variance."

        elif reason_code == CanonicalReasonCode.MISSING_BANK_SETTLEMENT:
            exp = (
                f"Payment captured via Gateway for ₹{gw_gross:,.2f} on {ctx.get('gateway_date', 'recent')}, "
                f"but corresponding bank settlement deposit has not been received (missing bank credit)."
            )
            action = "Trace bank settlement UTR with payment aggregator."

        elif reason_code == CanonicalReasonCode.MISSING_GATEWAY_TRANSACTION:
            exp = f"ERP Invoice on reference '{ref}' for ₹{inv_amt:,.2f} has no corresponding payment gateway collection."
            action = f"Locate payment gateway collection or follow up on customer payment from {cust}."

        elif reason_code in (CanonicalReasonCode.MISSING_INVOICE, CanonicalReasonCode.UNALLOCATED_DEPOSIT):
            exp = (
                f"Unallocated bank deposit of ₹{bank_credit:,.2f} on {ctx.get('bank_date', 'recent')} "
                f"with no corresponding ERP invoice or gateway payment record found."
            )
            action = "Identify remittance entity and allocate to accounts receivable subledger."

        elif reason_code == CanonicalReasonCode.DUPLICATE_TRANSACTION:
            exp = f"Duplicate transaction detected: multiple records sharing reference '{ref}' for ₹{gw_gross:,.2f}."
            action = "Review duplicate submission and void redundant capture if necessary."

        elif reason_code == CanonicalReasonCode.DATE_OUTSIDE_TOLERANCE:
            exp = f"Date discrepancy: settlement clearing gap of {delta_days} days exceeds allowable tolerance window."
            action = "Verify settlement lag and banking clearance delay."

        elif reason_code == CanonicalReasonCode.MATERIALITY_EXCEEDED:
            exp = f"Material discrepancy of ₹{variance:,.2f} exceeds auto-clear threshold and requires supervisor review."
            action = "Controller sign-off required."

        elif reason_code == CanonicalReasonCode.FEE_VARIANCE:
            exp = f"Gateway fee variance of ₹{fee:,.2f} ({variance:,.2f} difference) requires manual confirmation."
            action = "Verify gateway contractual fee schedule."

        else:
            exp = f"Discrepancy tagged under '{reason_code}' requiring human controller review."
            action = "Operator review required."

        return {"explanation": exp, "recommended_action": action}
