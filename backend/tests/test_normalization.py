"""
Unit tests for NormalizationService.
"""

from datetime import date
from app.services.normalization import NormalizationService


def test_customer_name_normalization():
    # Legal suffix stripping
    assert NormalizationService.normalize_customer_name("Acme Technologies Pvt. Ltd.") == "acme"
    assert NormalizationService.normalize_customer_name("NEXUS RETAIL SOLUTIONS INDIA") == "nexus retail"
    assert NormalizationService.normalize_customer_name("Apex Global Logistics Ltd") == "apex global logistics"
    assert NormalizationService.normalize_customer_name("Vortex Mfg Pvt Ltd") == "vortex mfg"
    assert NormalizationService.normalize_customer_name("Acme Private Limited") == "acme"
    assert NormalizationService.normalize_customer_name(None) == ""


def test_reference_normalization():
    # Prefix and punctuation stripping + leading zero stripping
    assert NormalizationService.normalize_reference("REF-83921") == "83921"
    assert NormalizationService.normalize_reference("PAY-83921") == "83921"
    assert NormalizationService.normalize_reference("INV/2026/83921") == "202683921"
    assert NormalizationService.normalize_reference("PG_83921") == "83921"
    assert NormalizationService.normalize_reference("txn-994812") == "994812"
    assert NormalizationService.normalize_reference("83921") == "83921"
    assert NormalizationService.normalize_reference("") == ""
    # Fix 1 assertions:
    assert NormalizationService.normalize_reference("INV-0042") == "42"
    assert NormalizationService.normalize_reference("INV-42") == "42"
    assert NormalizationService.normalize_reference("INV-0042") == NormalizationService.normalize_reference("INV-42")
    assert NormalizationService.normalize_reference("ORD-0005001") == "5001"


def test_amount_normalization():
    assert NormalizationService.normalize_amount("₹12,500.50") == 12500.50
    assert NormalizationService.normalize_amount("$450.00") == 450.00
    assert NormalizationService.normalize_amount("USD 100.00") == 100.00
    assert NormalizationService.normalize_amount("EUR 2,500.00") == 2500.00
    # Fix 1: Parentheses for negative
    assert NormalizationService.normalize_amount("(100.00)") == -100.00
    assert NormalizationService.normalize_amount("(500.50)") == -500.50
    # Fix 1: Preserve sign
    assert NormalizationService.normalize_amount(-450.00) == -450.00
    assert NormalizationService.normalize_amount("-1,200.75") == -1200.75
    # Fix 1: European decimals
    assert NormalizationService.normalize_amount("1.234,56", decimal_format="european") == 1234.56
    # Direction support
    assert NormalizationService.normalize_amount(300.00, direction="debit") == -300.00
    assert NormalizationService.normalize_amount("invalid") == 0.0
    assert NormalizationService.normalize_amount(None) == 0.0


def test_date_normalization():
    assert NormalizationService.normalize_date("2026-08-24") == date(2026, 8, 24)
    assert NormalizationService.normalize_date("24/08/2026") == date(2026, 8, 24)
    assert NormalizationService.normalize_date(date(2026, 8, 24)) == date(2026, 8, 24)
    # Fix 1: Explicit date format parsing
    assert NormalizationService.normalize_date("01/12/2026", date_format="%d/%m/%Y") == date(2026, 12, 1)
    assert NormalizationService.normalize_date("12/01/2026", date_format="%m/%d/%Y") == date(2026, 12, 1)
