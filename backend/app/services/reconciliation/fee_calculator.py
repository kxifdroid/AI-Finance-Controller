"""
Fee and Tax Calculation Service for Payment Gateway Settlement Reconciliation.

Problem Solved:
Deterministically computes payment gateway fee deductions, applicable GST/tax on fees,
and expected net bank settlements, and evaluates whether bank deposit amounts match
contractual fee schedules.

Why It Exists:
To enforce exact arithmetic calculations for MDR (Merchant Discount Rate), GST (18% on gateway fee),
and net settlement reconciliation without relying on non-deterministic LLM arithmetic.

Input:
Gross transaction amount, gateway fee, GST/tax amount, and actual bank settlement amount.

Output:
Deterministic calculations and variance classifications (FEE_RECONCILED, FEE_VARIANCE, FEE_MISMATCH).
"""

from typing import Tuple, Optional
from app.config import settings


class FeeCalculator:
    """
    Deterministic calculation engine for payment gateway fees, tax deductions, and settlement variances.
    """

    @staticmethod
    def calculate_fee_settlement(
        gross_amount: float,
        fee_amount: float,
        tax_amount: float,
    ) -> float:
        """
        Calculates the expected net settlement amount disbursed to the bank:
        expected_net = gross_amount - fee_amount - tax_amount.

        Args:
            gross_amount: Total invoiced / charged customer amount.
            fee_amount: Payment gateway MDR / processing fee.
            tax_amount: GST / VAT applied to the gateway processing fee.

        Returns:
            Rounded float representing the expected net bank settlement.
        """
        gross = float(gross_amount or 0.0)
        fee = float(fee_amount or 0.0)
        tax = float(tax_amount or 0.0)
        return round(gross - fee - tax, 2)

    @staticmethod
    def calculate_gst_on_fee(fee_amount: float) -> float:
        """
        Calculates applicable Goods and Services Tax (GST) on payment gateway processing fee
        using the configured rate (default 18%).

        Args:
            fee_amount: Payment gateway fee before tax.

        Returns:
            Calculated tax amount rounded to 2 decimal places.
        """
        fee = float(fee_amount or 0.0)
        return round(fee * settings.GST_RATE_ON_GATEWAY_FEE, 2)

    @classmethod
    def validate_fee_variance(
        cls,
        gross_amount: float,
        actual_bank_credit: float,
        fee_amount: Optional[float] = None,
        tax_amount: Optional[float] = None,
    ) -> Tuple[bool, float, float, str]:
        """
        Validates the variance between gross gateway collection and actual bank settlement.

        Args:
            gross_amount: Initial gross amount recorded by gateway.
            actual_bank_credit: Net amount credited in bank statement.
            fee_amount: Optional recorded gateway fee.
            tax_amount: Optional recorded tax on fee.

        Returns:
            Tuple of:
            - is_valid (bool): Whether the variance is within permissible tolerance or exact reconciliation.
            - fee_pct (float): Effective fee percentage (e.g. 0.0236 for 2.36%).
            - variance (float): Monetary difference between expected net and actual bank credit.
            - classification (str): 'FEE_RECONCILED' | 'FEE_VARIANCE' | 'FEE_MISMATCH'.
        """
        gross = float(gross_amount or 0.0)
        actual = float(actual_bank_credit or 0.0)

        if gross <= 0:
            return (False, 0.0, round(actual - gross, 2), "FEE_MISMATCH")

        # When recorded fee and tax are provided
        if fee_amount is not None and tax_amount is not None:
            expected_net = cls.calculate_fee_settlement(gross, fee_amount, tax_amount)
            variance = round(actual - expected_net, 2)
            fee_pct = round((gross - actual) / gross, 4)

            if abs(variance) < 0.01:
                return (True, fee_pct, variance, "FEE_RECONCILED")
            elif settings.FEE_VARIANCE_MIN_PCT <= fee_pct <= settings.FEE_VARIANCE_MAX_PCT:
                return (True, fee_pct, variance, "FEE_VARIANCE")
            else:
                return (False, fee_pct, variance, "FEE_MISMATCH")
        else:
            # Implied fee from difference between gross collection and bank credit
            implied_fee = round(gross - actual, 2)
            fee_pct = round(implied_fee / gross, 4)
            variance = implied_fee

            if abs(implied_fee) < 0.01:
                return (True, 0.0, 0.0, "FEE_RECONCILED")
            elif settings.FEE_VARIANCE_MIN_PCT <= fee_pct <= settings.FEE_VARIANCE_MAX_PCT:
                return (True, fee_pct, variance, "FEE_VARIANCE")
            else:
                return (False, fee_pct, variance, "FEE_MISMATCH")
