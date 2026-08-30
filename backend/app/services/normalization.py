"""
Normalization Service for Financial Data.

Problem Solved:
Financial records from disparate sources (Banks, Payment Gateways, Invoices)
contain pervasive formatting inconsistencies:
1. Company names contain legal suffixes (e.g. 'Pvt Ltd', 'LLC', 'Inc', 'Private Limited').
2. Reference IDs include arbitrary prefixes ('REF-', 'PAY-', 'INV/', 'PG_', 'ORD-') or punctuation, and leading zeros.
3. Dates vary across formats (ISO-8601, DD/MM/YYYY, MM/DD/YYYY).
4. Amounts may contain currency symbols, commas, parentheses for negatives, or European comma decimals.

Why It Exists:
To transform raw input strings into normalized, canonical representations while
preserving the original values for human operator auditability and deterministic matching.
"""

import re
from datetime import date, datetime
from typing import Union, Optional
from dateutil import parser as date_parser


# Common legal company suffixes to strip during entity normalization
LEGAL_SUFFIXES_REGEX = re.compile(
    r"\b(pvt\.?\s*ltd\.?|private\s+limited|ltd\.?|limited|inc\.?|incorporated|"
    r"llc|corp\.?|corporation|co\.?|solutions|services|india|technologies|tech)\b",
    flags=re.IGNORECASE
)

# Reference cleanup pattern: strip non-alphanumeric except common core markers
NON_ALPHANUMERIC_REGEX = re.compile(r"[^A-Za-z0-9]")

# Transaction reference prefix pattern
REF_PREFIX_REGEX = re.compile(
    r"^(ref|inv|pay|pg|txn|upi|neft|rtgs|cms|cr|dr|ord|order)[\-_/\s:]*",
    flags=re.IGNORECASE
)

# Currency prefixes and symbols
CURRENCY_CLEANUP_REGEX = re.compile(r"\b(USD|EUR|INR|GBP|CAD|AUD|JPY|CHF)\b|[₹$€£,]", flags=re.IGNORECASE)


class NormalizationService:
    """
    Provides stateless normalization functions for financial entities.
    """

    @staticmethod
    def normalize_customer_name(name: Optional[str]) -> str:
        """
        Normalizes a business/customer name by removing legal entity suffixes,
        punctuation, and excess whitespace.
        
        Example:
        'Acme Technologies Pvt. Ltd.' -> 'acme'
        'NEXUS RETAIL SOLUTIONS INDIA' -> 'nexus retail'
        """
        if not name or not isinstance(name, str):
            return ""
        
        # 1. Lowercase and remove punctuation
        cleaned = name.lower()
        cleaned = LEGAL_SUFFIXES_REGEX.sub("", cleaned)
        cleaned = re.sub(r"[^\w\s]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        
        # Fallback to original cleaned string if stripping removed everything
        if not cleaned:
            return re.sub(r"\s+", " ", name.lower()).strip()
        return cleaned

    @staticmethod
    def normalize_reference(ref: Optional[str]) -> str:
        """
        Extracts the canonical core identifier from arbitrary reference strings,
        stripping prefixes, punctuation, and leading zeros.
        
        Examples:
        'REF-83921' -> '83921'
        'INV-0042' -> '42'
        'INV-42'   -> '42'
        'INV/2026/83921' -> '202683921'
        'PG_0009999' -> '9999'
        """
        if not ref or not isinstance(ref, str):
            return ""
        
        cleaned = ref.strip().lower()
        # Remove known transaction prefixes
        cleaned = REF_PREFIX_REGEX.sub("", cleaned)
        # Strip all punctuation/spaces
        core_alphanumeric = NON_ALPHANUMERIC_REGEX.sub("", cleaned)
        
        if not core_alphanumeric:
            return cleaned
        
        # Strip leading zeros so 'INV-0042' and 'INV-42' normalize to '42'
        stripped_zeros = core_alphanumeric.lstrip("0")
        return stripped_zeros if stripped_zeros else "0"

    @staticmethod
    def normalize_amount(
        amount: Union[int, float, str],
        decimal_format: str = "standard",
        direction: Optional[str] = None
    ) -> float:
        """
        Parses and standardizes amounts preserving signs, rounded to 2 decimal places.
        Supports currency codes, parentheses for negative numbers, and European decimals.
        
        Examples:
        '₹12,500.50' -> 12500.50
        '(100.00)'   -> -100.00
        'USD 100.00' -> 100.00
        '1.234,56' (european) -> 1234.56
        -450.00      -> -450.00
        """
        if amount is None:
            return 0.0
        
        if isinstance(amount, (int, float)):
            val = float(amount)
            if direction and direction.lower() == "debit" and val > 0:
                val = -val
            return round(val, 2)
        
        raw = str(amount).strip()
        if not raw:
            return 0.0
        
        # Check for parentheses indicating negative: (100.00) -> -100.00
        is_negative = False
        if raw.startswith("(") and raw.endswith(")"):
            is_negative = True
            raw = raw[1:-1].strip()
        elif raw.startswith("-"):
            is_negative = True
            raw = raw[1:].strip()
        elif raw.endswith("-"):
            is_negative = True
            raw = raw[:-1].strip()
        elif direction and direction.lower() == "debit":
            is_negative = True

        # Handle European decimal formatting: "1.234,56" -> "1234.56"
        if decimal_format == "european":
            raw = raw.replace(".", "").replace(",", ".")
        else:
            # Standard formatting: strip commas
            raw = raw.replace(",", "")
        
        # Strip currency symbols and letters
        cleaned = CURRENCY_CLEANUP_REGEX.sub("", raw).strip()
        
        try:
            val = float(cleaned)
            if is_negative:
                val = -val
            return round(val, 2)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def normalize_date(
        dt: Union[str, date, datetime],
        date_format: Optional[str] = None
    ) -> date:
        """
        Parses date into a standard datetime.date object.
        If date_format is specified, uses strict strptime parsing.
        """
        if isinstance(dt, date) and not isinstance(dt, datetime):
            return dt
        if isinstance(dt, datetime):
            return dt.date()
        
        if not dt or not isinstance(dt, str):
            return date.today()
        
        dt_str = dt.strip()
        if not dt_str:
            return date.today()

        # 1. Try explicit format if provided
        if date_format:
            try:
                return datetime.strptime(dt_str, date_format).date()
            except Exception:
                pass
        
        # 2. Try standard ISO format (YYYY-MM-DD)
        try:
            return date.fromisoformat(dt_str)
        except Exception:
            pass

        # 3. Fallback date parser
        try:
            parsed = date_parser.parse(dt_str, dayfirst=False)
            return parsed.date()
        except Exception:
            try:
                parsed = date_parser.parse(dt_str, dayfirst=True)
                return parsed.date()
            except Exception:
                return date.today()

    @staticmethod
    def normalize_description(desc: Optional[str]) -> str:
        """
        Normalizes transaction descriptions by collapsing spaces and stripping special chars.
        """
        if not desc or not isinstance(desc, str):
            return ""
        cleaned = re.sub(r"[^\w\s]", " ", desc.lower())
        return re.sub(r"\s+", " ", cleaned).strip()
