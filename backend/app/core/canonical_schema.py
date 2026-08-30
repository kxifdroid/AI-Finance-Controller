"""
Canonical Financial Data Schema Definitions.

This module is the SINGLE SOURCE OF TRUTH for all canonical field definitions
across the reconciliation system. All schema definitions, required fields,
synonyms, and validation rules must be defined here and imported elsewhere.

CRITICAL ARCHITECTURE PRINCIPLE:
The LLM must NEVER perform authoritative financial arithmetic. All financial
calculations must be deterministic Python/SQL. The LLM/agent is only responsible
for understanding user intent, selecting tools, investigating issues, interpreting
deterministic tool results, explaining findings, recommending actions, and
requesting human approval for sensitive/write actions.
"""

from typing import Dict, List, Any, Optional, Set
from enum import Enum
from decimal import Decimal
from datetime import date
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# DATA SOURCE TYPES
# =============================================================================

class DataSourceType(str, Enum):
    """Canonical data source type identifiers."""
    INVOICE = "INVOICE"       # ERP/Accounting system invoices
    GATEWAY = "GATEWAY"       # Payment gateway transactions (Razorpay, Stripe, etc.)
    BANK = "BANK"             # Bank statement transactions


# =============================================================================
# CANONICAL FIELD DEFINITIONS
# =============================================================================

# Each field definition includes:
# - required: Whether the field is mandatory for ingestion
# - synonyms: Common column name variations that map to this field
# - excludes: Column names that should NOT map to this field (prevent mismatches)
# - description: Human-readable description for UI/docs
# - data_type: Expected Python type for validation

INVOICE_SCHEMA: Dict[str, Dict[str, Any]] = {
    "invoice_id": {
        "required": True,
        "synonyms": [
            "invoice id", "invoice number", "inv id", "inv no", "invoice_id",
            "invoiceno", "invoice_no", "inv_num", "bill id", "bill no", "invoice #",
            "invoice ref", "document number", "doc no", "invoice num"
        ],
        "excludes": [
            "order id", "order number", "order_id", "order_no", "po number",
            "po_id", "purchase order", "gateway", "payment", "bank", "txn"
        ],
        "description": "Unique ERP invoice identifier",
        "data_type": "str"
    },
    "invoice_date": {
        "required": True,
        "synonyms": [
            "invoice date", "inv date", "date", "billing date", "invoice_date",
            "issue date", "bill date", "created at", "doc date", "document date"
        ],
        "excludes": ["due date", "payment date", "expiry date", "transaction date"],
        "description": "Date the invoice was issued",
        "data_type": "date"
    },
    "amount": {
        "required": True,
        "synonyms": [
            "amount", "total amount", "invoice amount", "grand total", "net amount",
            "total", "billed amount", "invoice_amount", "gross amount", "invoice total",
            "final amount", "payable amount", "total value"
        ],
        "excludes": [
            "tax", "fee", "discount", "qty", "quantity", "price", "unit price",
            "balance", "paid amount", "gateway fee"
        ],
        "description": "Total invoice amount (gross)",
        "data_type": "decimal"
    },
    "order_id": {
        "required": False,
        "synonyms": [
            "order id", "order number", "order_id", "order_no", "purchase order",
            "po number", "po_id", "sales order", "so number", "reference number"
        ],
        "excludes": ["invoice id", "invoice number", "inv id", "inv no", "payment id"],
        "description": "Related sales order or PO number",
        "data_type": "str"
    },
    "invoice_reference": {
        "required": False,
        "synonyms": [
            "invoice reference", "reference", "ref id", "ref no", "reference_id",
            "ref", "memo", "notes", "external ref", "customer ref"
        ],
        "excludes": ["invoice id", "invoice number", "inv id", "inv no"],
        "description": "Secondary reference code or memo",
        "data_type": "str"
    },
    "customer_name": {
        "required": False,
        "synonyms": [
            "customer name", "client name", "customer", "client", "buyer",
            "customer_name", "account name", "bill to", "party name", "company name"
        ],
        "excludes": ["vendor", "seller", "merchant", "supplier"],
        "description": "Customer or buyer company name",
        "data_type": "str"
    },
    "customer_id": {
        "required": False,
        "synonyms": [
            "customer id", "customer_id", "client id", "account id",
            "buyer id", "party id", "account number"
        ],
        "excludes": ["invoice id", "order id"],
        "description": "Internal customer/account identifier",
        "data_type": "str"
    },
    "customer_email": {
        "required": False,
        "synonyms": [
            "customer email", "email", "client email", "email address",
            "customer_email", "contact email"
        ],
        "excludes": ["name", "phone", "address"],
        "description": "Customer email address",
        "data_type": "str"
    },
    "tax_amount": {
        "required": False,
        "synonyms": [
            "tax", "tax amount", "gst", "vat", "tax_amount",
            "cgst", "sgst", "igst", "tax total", "gst amount"
        ],
        "excludes": ["amount", "total", "net", "gross", "invoice amount"],
        "description": "Tax/GST component of the invoice",
        "data_type": "decimal"
    },
    "currency": {
        "required": False,
        "synonyms": ["currency", "currency code", "ccy", "curr"],
        "excludes": ["amount", "total"],
        "description": "Currency code (default INR)",
        "data_type": "str"
    },
    "due_date": {
        "required": False,
        "synonyms": [
            "due date", "due_date", "payment due", "due by", "payable date"
        ],
        "excludes": ["invoice date", "billing date", "created at"],
        "description": "Payment due date",
        "data_type": "date"
    },
    "status": {
        "required": False,
        "synonyms": [
            "status", "invoice status", "payment status", "state"
        ],
        "excludes": [],
        "description": "Invoice payment/processing status",
        "data_type": "str"
    }
}

GATEWAY_SCHEMA: Dict[str, Dict[str, Any]] = {
    "gateway_txn_id": {
        "required": True,
        "synonyms": [
            "gateway transaction id", "txn id", "transaction id", "payment id",
            "gateway_txn_id", "gateway txn id", "payment_id", "charge id",
            "pg_txn_id", "stripe id", "razorpay_payment_id", "transaction_id",
            "payment reference", "capture id", "pg id"
        ],
        "excludes": ["order id", "order number", "invoice id", "invoice number", "bank"],
        "description": "Payment gateway transaction/capture ID",
        "data_type": "str"
    },
    "transaction_date": {
        "required": True,
        "synonyms": [
            "transaction date", "txn date", "date", "created at", "payment date",
            "transaction_date", "captured_at", "paid at", "capture date",
            "payment timestamp", "created date"
        ],
        "excludes": ["settlement date", "expiry date"],
        "description": "Payment capture/transaction date",
        "data_type": "date"
    },
    "gross_amount": {
        "required": True,
        "synonyms": [
            "amount", "gross amount", "order amount", "billed amount",
            "amount_gross", "gross_amount", "captured amount", "charge amount",
            "txn amount", "payment amount", "total amount"
        ],
        "excludes": [
            "net amount", "fee", "tax", "payout", "settlement", "net_amount",
            "gateway fee", "net settlement"
        ],
        "description": "Original gross payment amount before fees",
        "data_type": "decimal"
    },
    "net_amount": {
        "required": False,
        "synonyms": [
            "net amount", "settlement amount", "amount after fee", "payout amount",
            "net_amount", "net_settlement", "settled amount", "net payout",
            "disbursed amount"
        ],
        "excludes": ["gross amount", "fee", "gateway fee", "tax", "charge amount"],
        "description": "Net settlement amount after fees/taxes",
        "data_type": "decimal"
    },
    "gateway_fee": {
        "required": False,
        "synonyms": [
            "fee", "gateway fee", "commission", "charges", "gateway_fee",
            "processing fee", "mdr", "service fee", "fee amount", "pg fee",
            "merchant discount rate"
        ],
        "excludes": ["net amount", "gross amount", "amount", "order amount"],
        "description": "Gateway processing fee (MDR)",
        "data_type": "decimal"
    },
    "tax_on_fee": {
        "required": False,
        "synonyms": [
            "tax", "tax on fee", "tax_on_fee", "gst", "vat", "service tax",
            "tax amount", "gst on fee", "fee tax"
        ],
        "excludes": ["amount", "gross", "net", "gross amount", "net amount"],
        "description": "Tax (GST) on gateway processing fee",
        "data_type": "decimal"
    },
    "payment_reference": {
        "required": False,
        "synonyms": [
            "order id", "order number", "order_id", "order_no", "ord id",
            "payment reference", "payment_reference", "merchant_order_id",
            "reference_id", "reference", "ref", "merchant ref"
        ],
        "excludes": ["gateway transaction id", "txn id", "charge id", "payment id"],
        "description": "Merchant order/reference ID",
        "data_type": "str"
    },
    "gateway_order_id": {
        "required": False,
        "synonyms": [
            "gateway order id", "razorpay order id", "stripe order",
            "gateway_order_id", "pg order id"
        ],
        "excludes": ["payment id", "txn id", "merchant order"],
        "description": "Gateway-side order ID (e.g., razorpay_order_id)",
        "data_type": "str"
    },
    "customer_name": {
        "required": False,
        "synonyms": [
            "customer", "customer name", "payer", "cardholder", "buyer",
            "account holder", "payer name"
        ],
        "excludes": ["merchant", "vendor"],
        "description": "Customer/payer name",
        "data_type": "str"
    },
    "payment_method": {
        "required": False,
        "synonyms": [
            "payment method", "method", "payment type", "instrument",
            "payment_method", "mode"
        ],
        "excludes": [],
        "description": "Payment method (UPI, Card, Net Banking, Wallet)",
        "data_type": "str"
    },
    "currency": {
        "required": False,
        "synonyms": ["currency", "currency code", "ccy", "curr"],
        "excludes": ["amount", "total"],
        "description": "Currency code (default INR)",
        "data_type": "str"
    },
    "status": {
        "required": False,
        "synonyms": [
            "status", "payment status", "txn status", "transaction status",
            "capture status", "state"
        ],
        "excludes": [],
        "description": "Payment status (captured, failed, refunded, etc.)",
        "data_type": "str"
    }
}

BANK_SCHEMA: Dict[str, Dict[str, Any]] = {
    "bank_txn_id": {
        "required": True,
        "synonyms": [
            "bank transaction id", "txn id", "transaction id", "bank_txn_id",
            "reference number", "ref no", "transaction reference", "bank ref",
            "statement id", "line id", "entry id", "serial no"
        ],
        "excludes": ["utr", "payment id", "invoice id", "gateway"],
        "description": "Unique bank statement line identifier",
        "data_type": "str"
    },
    "transaction_date": {
        "required": True,
        "synonyms": [
            "transaction date", "date", "txn date", "statement date",
            "transaction_date", "posting date", "entry date", "book date"
        ],
        "excludes": ["value date"],
        "description": "Bank statement transaction date",
        "data_type": "date"
    },
    "amount": {
        "required": True,
        "synonyms": [
            "amount", "credit amount", "deposit amount", "credit",
            "transaction amount", "txn amount", "value"
        ],
        "excludes": ["debit", "withdrawal", "balance", "fee"],
        "description": "Credit/deposit amount",
        "data_type": "decimal"
    },
    "utr": {
        "required": False,
        "synonyms": [
            "utr", "utr number", "utr no", "unique transaction reference",
            "settlement ref", "settlement reference", "imps ref", "neft ref",
            "rtgs ref"
        ],
        "excludes": ["bank txn id", "transaction id"],
        "description": "Unique Transaction Reference (UTR) number",
        "data_type": "str"
    },
    "reference": {
        "required": False,
        "synonyms": [
            "reference", "ref", "narration", "description", "memo",
            "payment reference", "cheque no", "remarks"
        ],
        "excludes": ["utr", "bank txn id"],
        "description": "Bank narration/reference text",
        "data_type": "str"
    },
    "description": {
        "required": False,
        "synonyms": [
            "description", "narration", "particulars", "details",
            "transaction description", "memo", "remarks"
        ],
        "excludes": [],
        "description": "Detailed bank statement narration",
        "data_type": "str"
    },
    "credit_amount": {
        "required": False,
        "synonyms": [
            "credit", "credit amount", "deposit", "inflow", "cr",
            "credit value", "money in"
        ],
        "excludes": ["debit", "withdrawal", "balance"],
        "description": "Credit/deposit amount (if separate column)",
        "data_type": "decimal"
    },
    "debit_amount": {
        "required": False,
        "synonyms": [
            "debit", "debit amount", "withdrawal", "outflow", "dr",
            "debit value", "money out"
        ],
        "excludes": ["credit", "deposit", "balance"],
        "description": "Debit/withdrawal amount (if separate column)",
        "data_type": "decimal"
    },
    "value_date": {
        "required": False,
        "synonyms": [
            "value date", "value_date", "clearing date", "settlement date"
        ],
        "excludes": ["transaction date", "posting date"],
        "description": "Value/clearing date",
        "data_type": "date"
    },
    "balance": {
        "required": False,
        "synonyms": [
            "balance", "closing balance", "running balance", "available balance",
            "ledger balance"
        ],
        "excludes": ["amount", "credit", "debit"],
        "description": "Account balance after transaction",
        "data_type": "decimal"
    },
    "currency": {
        "required": False,
        "synonyms": ["currency", "currency code", "ccy", "curr"],
        "excludes": ["amount", "total"],
        "description": "Currency code (default INR)",
        "data_type": "str"
    }
}


# =============================================================================
# SCHEMA REGISTRY
# =============================================================================

CANONICAL_SCHEMAS: Dict[str, Dict[str, Dict[str, Any]]] = {
    DataSourceType.INVOICE.value: INVOICE_SCHEMA,
    DataSourceType.GATEWAY.value: GATEWAY_SCHEMA,
    DataSourceType.BANK.value: BANK_SCHEMA,
}


def get_schema(data_type: str) -> Dict[str, Dict[str, Any]]:
    """Get the canonical schema for a data source type."""
    return CANONICAL_SCHEMAS.get(data_type.upper(), {})


def get_required_fields(data_type: str) -> List[str]:
    """Get list of required fields for a data source type."""
    schema = get_schema(data_type)
    return [field for field, spec in schema.items() if spec.get("required", False)]


def get_all_fields(data_type: str) -> List[str]:
    """Get all field names for a data source type."""
    return list(get_schema(data_type).keys())


def get_field_synonyms(data_type: str, field_name: str) -> List[str]:
    """Get synonyms for a specific field."""
    schema = get_schema(data_type)
    field_spec = schema.get(field_name, {})
    return field_spec.get("synonyms", [])


def get_field_excludes(data_type: str, field_name: str) -> List[str]:
    """Get exclusion patterns for a specific field."""
    schema = get_schema(data_type)
    field_spec = schema.get(field_name, {})
    return field_spec.get("excludes", [])


# =============================================================================
# EXCEPTION TAXONOMY
# =============================================================================

class ExceptionType(str, Enum):
    """Canonical exception type identifiers for financial reconciliation."""
    
    # Missing record exceptions
    MISSING_ERP_TRANSACTION = "MISSING_ERP_TRANSACTION"
    MISSING_GATEWAY_TRANSACTION = "MISSING_GATEWAY_TRANSACTION"
    MISSING_BANK_SETTLEMENT = "MISSING_BANK_SETTLEMENT"
    
    # Duplicate exceptions
    DUPLICATE_TRANSACTION = "DUPLICATE_TRANSACTION"
    
    # Amount exceptions
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    FEE_MISMATCH = "FEE_MISMATCH"
    FEE_VARIANCE = "FEE_VARIANCE"
    TAX_MISMATCH = "TAX_MISMATCH"
    PARTIAL_SETTLEMENT = "PARTIAL_SETTLEMENT"
    
    # Timing exceptions
    DATE_MISMATCH = "DATE_MISMATCH"
    TIMING_DIFFERENCE = "TIMING_DIFFERENCE"
    
    # Settlement exceptions
    MANY_TO_ONE_SETTLEMENT = "MANY_TO_ONE_SETTLEMENT"
    ONE_TO_MANY_TRANSACTION = "ONE_TO_MANY_TRANSACTION"
    
    # Status exceptions
    STATUS_MISMATCH = "STATUS_MISMATCH"
    REFUND = "REFUND"
    
    # Generic
    NO_MATCH_FOUND = "NO_MATCH_FOUND"
    UNKNOWN = "UNKNOWN"


VALID_EXCEPTION_TYPES: Set[str] = {e.value for e in ExceptionType}


# =============================================================================
# SEVERITY LEVELS
# =============================================================================

class SeverityLevel(str, Enum):
    """Exception severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# =============================================================================
# APPROVAL STATUS
# =============================================================================

class ApprovalStatus(str, Enum):
    """Human approval workflow status."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class ApprovalActionType(str, Enum):
    """Types of actions requiring human approval."""
    MARK_RECONCILED = "MARK_RECONCILED"
    WRITE_OFF_VARIANCE = "WRITE_OFF_VARIANCE"
    CREATE_ADJUSTMENT = "CREATE_ADJUSTMENT"
    EXPORT_FINAL_REPORT = "EXPORT_FINAL_REPORT"
    VOID_DUPLICATE = "VOID_DUPLICATE"
    MANUAL_MATCH = "MANUAL_MATCH"


# =============================================================================
# PYDANTIC MODELS FOR CANONICAL TRANSACTIONS
# =============================================================================

class CanonicalInvoice(BaseModel):
    """Normalized invoice record."""
    invoice_id: str
    invoice_date: date
    amount: Decimal
    order_id: Optional[str] = None
    invoice_reference: Optional[str] = None
    customer_name: Optional[str] = None
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    tax_amount: Optional[Decimal] = None
    currency: str = "INR"
    due_date: Optional[date] = None
    status: Optional[str] = None
    
    # Metadata
    source_file_id: Optional[str] = None
    source_row_id: Optional[int] = None
    dataset_id: Optional[str] = None


class CanonicalGatewayTransaction(BaseModel):
    """Normalized payment gateway transaction record."""
    gateway_txn_id: str
    transaction_date: date
    gross_amount: Decimal
    net_amount: Optional[Decimal] = None
    gateway_fee: Optional[Decimal] = None
    tax_on_fee: Optional[Decimal] = None
    payment_reference: Optional[str] = None
    gateway_order_id: Optional[str] = None
    customer_name: Optional[str] = None
    payment_method: Optional[str] = None
    currency: str = "INR"
    status: Optional[str] = None
    
    # Metadata
    source_file_id: Optional[str] = None
    source_row_id: Optional[int] = None
    dataset_id: Optional[str] = None
    
    @field_validator('net_amount', mode='before')
    @classmethod
    def compute_net_amount(cls, v, info):
        """Auto-compute net amount if not provided."""
        if v is None:
            gross = info.data.get('gross_amount')
            fee = info.data.get('gateway_fee') or Decimal('0')
            tax = info.data.get('tax_on_fee') or Decimal('0')
            if gross:
                return gross - fee - tax
        return v


class CanonicalBankTransaction(BaseModel):
    """Normalized bank statement transaction record."""
    bank_txn_id: str
    transaction_date: date
    amount: Decimal
    utr: Optional[str] = None
    reference: Optional[str] = None
    description: Optional[str] = None
    credit_amount: Optional[Decimal] = None
    debit_amount: Optional[Decimal] = None
    value_date: Optional[date] = None
    balance: Optional[Decimal] = None
    currency: str = "INR"
    
    # Metadata
    source_file_id: Optional[str] = None
    source_row_id: Optional[int] = None
    dataset_id: Optional[str] = None


# =============================================================================
# MAPPING CONTRACT
# =============================================================================

class MappingContract(BaseModel):
    """
    Mapping contract between source file columns and canonical schema.
    
    The mapping direction is: canonical_field -> source_column
    e.g., {"invoice_id": "Invoice Number", "amount": "Total Amount"}
    """
    file_id: str
    filename: str
    file_type: str  # csv, xlsx, xls
    data_type: str  # INVOICE, GATEWAY, BANK
    mapping: Dict[str, str]  # canonical_field -> source_column
    
    def get_source_column(self, canonical_field: str) -> Optional[str]:
        """Get the source column mapped to a canonical field."""
        return self.mapping.get(canonical_field)
    
    def validate_required_fields(self) -> List[str]:
        """Returns list of missing required fields."""
        required = get_required_fields(self.data_type)
        missing = []
        for field in required:
            mapped_col = self.mapping.get(field)
            if not mapped_col or not str(mapped_col).strip():
                missing.append(field)
        return missing
    
    def to_rename_dict(self) -> Dict[str, str]:
        """
        Convert mapping to pandas rename format: source_col -> canonical_field.
        """
        return {v: k for k, v in self.mapping.items() if v}
