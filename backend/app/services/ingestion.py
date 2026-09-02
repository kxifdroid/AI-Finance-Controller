"""
Data Ingestion Service for Multi-Source Financial Records.

Problem Solved:
Validates, normalizes, deduplicates, and ingests financial records from Bank Statements,
Payment Gateway Logs, and ERP Invoices with idempotent insert-or-skip semantics and
explicit synonym-based column mapping.

Why It Exists:
To enforce schema validation, eliminate duplicate row insertions on repeated runs,
and provide deterministic, transparent column mapping with strict exclusion vetoes.
"""

import io
import re
import hashlib
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from sqlalchemy.orm import Session
from rapidfuzz import fuzz

from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.services.normalization import NormalizationService
from app.services.audit import AuditService


# Explicit target schemas with dedicated synonym lists and hard exclusion vetoes
TARGET_SCHEMAS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "INVOICE": {
        "invoice_id": {
            "required": True,
            "synonyms": [
                "invoice id", "invoice number", "inv id", "inv no", "invoice_id", 
                "invoiceno", "invoice_no", "inv_num", "bill id", "bill no", "invoice #"
            ],
            "excludes": ["order id", "order number", "order_id", "order_no", "po number", "po_id", "purchase order"]
        },
        "invoice_reference": {
            "required": False,
            "synonyms": [
                "order id", "order number", "order_id", "order_no", "invoice reference", 
                "reference", "ref id", "ref no", "po number", "customer po", "reference_id", "ref"
            ],
            "excludes": ["invoice id", "invoice number", "inv id", "inv no"]
        },
        "invoice_date": {
            "required": True,
            "synonyms": [
                "invoice date", "inv date", "date", "billing date", "invoice_date", 
                "issue date", "bill date", "created at", "doc date"
            ],
            "excludes": ["due date", "payment date", "expiry date"]
        },
        "amount": {
            "required": True,
            "synonyms": [
                "amount", "total amount", "invoice amount", "grand total", "net amount", 
                "total", "billed amount", "invoice_amount", "gross amount", "invoice total"
            ],
            "excludes": ["tax", "fee", "discount", "qty", "quantity", "price", "unit price", "balance"]
        },
        "customer_name": {
            "required": False,
            "synonyms": [
                "customer name", "client name", "customer", "client", "buyer", 
                "customer_name", "account name", "bill to", "party name"
            ],
            "excludes": ["vendor", "seller", "merchant", "supplier"]
        },
        "order_id": {
            "required": False,
            "synonyms": [
                "order id", "order number", "order_id", "order_no", "purchase order",
                "po number", "po_id", "sales order"
            ],
            "excludes": ["invoice id", "invoice number", "inv id", "inv no"]
        },
        "customer_id": {
            "required": False,
            "synonyms": [
                "customer id", "customer_id", "client id", "account id",
                "buyer id", "party id"
            ],
            "excludes": ["invoice id", "order id"]
        },
        "customer_email": {
            "required": False,
            "synonyms": [
                "customer email", "email", "client email", "email address",
                "customer_email", "contact email"
            ],
            "excludes": ["name", "phone", "address"]
        },
        "tax_amount": {
            "required": False,
            "synonyms": [
                "tax", "tax amount", "gst", "vat", "tax_amount",
                "cgst", "sgst", "igst", "tax total"
            ],
            "excludes": ["amount", "total", "net", "gross", "invoice amount"]
        },
        "currency": {
            "required": False,
            "synonyms": [
                "currency", "currency code", "ccy", "curr"
            ],
            "excludes": ["amount", "total"]
        },
        "due_date": {
            "required": False,
            "synonyms": [
                "due date", "due_date", "payment due", "due by", "payable date"
            ],
            "excludes": ["invoice date", "billing date", "created at"]
        }
    },
    "GATEWAY": {
        "gateway_txn_id": {
            "required": True,
            "synonyms": [
                "gateway transaction id", "gateway_transaction_id", "pg_txn_id", "razorpay_payment_id",
                "gateway_txn_id", "gateway txn id", "payment_id", "payment id", "charge id", 
                "stripe id", "transaction_id", "txn id", "transaction id"
            ],
            "excludes": ["order id", "order number", "invoice id", "invoice number"]
        },
        "payment_reference": {
            "required": False,
            "synonyms": [
                "order id", "order number", "order_id", "order_no", "ord id", 
                "payment reference", "payment_reference", "merchant_order_id", 
                "reference_id", "reference", "ref", "invoice id", "invoice_id", "inv id"
            ],
            "excludes": ["gateway transaction id", "charge id"]
        },
        "gross_amount": {
            "required": True,
            "synonyms": [
                "amount", "gross amount", "order amount", "billed amount", 
                "amount_gross", "gross_amount", "captured amount", "charge amount", "txn amount"
            ],
            "excludes": ["net amount", "fee", "tax", "payout", "settlement", "net_amount", "gateway fee"]
        },
        "net_amount": {
            "required": False,
            "synonyms": [
                "net amount", "settlement amount", "amount after fee", "payout amount", 
                "net_amount", "net_settlement", "settled amount", "net payout", "settlement_amount"
            ],
            "excludes": ["gross amount", "fee", "gateway fee", "tax", "charge amount"]
        },
        "gateway_fee": {
            "required": False,
            "synonyms": [
                "fee", "gateway fee", "commission", "charges", "gateway_fee", 
                "processing fee", "mdr", "service fee", "fee amount"
            ],
            "excludes": ["net amount", "gross amount", "amount", "order amount"]
        },
        "tax_on_fee": {
            "required": False,
            "synonyms": [
                "tax", "tax on fee", "tax_on_fee", "gst", "gst on fee", "gst_on_fee", "vat", "service tax", "tax amount"
            ],
            "excludes": ["amount", "gross", "net", "gross amount", "net amount"]
        },
        "transaction_date": {
            "required": True,
            "synonyms": [
                "transaction date", "txn date", "date", "created at", "payment date", "payment_date",
                "transaction_date", "captured_at", "paid at"
            ],
            "excludes": ["settlement date", "expiry date"]
        },
        "customer_name": {
            "required": False,
            "synonyms": [
                "customer name", "customer", "client", "payer", "cardholder", 
                "customer_name", "customer email", "payer name", "email"
            ],
            "excludes": ["gateway", "merchant", "processor"]
        },
        "gateway_order_id": {
            "required": False,
            "synonyms": [
                "razorpay order id", "razorpay_order_id", "gateway order id",
                "pg order id", "stripe_payment_intent", "checkout_id", "invoice id", "invoice_id", "settlement id", "settlement_id"
            ],
            "excludes": ["txn id", "transaction id"]
        },
        "payment_method": {
            "required": False,
            "synonyms": [
                "payment method", "method", "payment_method", "payment type",
                "payment mode", "instrument", "card type"
            ],
            "excludes": ["amount", "status", "reference"]
        },
        "currency": {
            "required": False,
            "synonyms": [
                "currency", "currency code", "ccy", "curr"
            ],
            "excludes": ["amount", "total"]
        },
        "gateway_name": {
            "required": False,
            "synonyms": [
                "gateway", "gateway name", "payment gateway", "processor",
                "pg name", "acquirer"
            ],
            "excludes": ["customer", "amount", "date"]
        },
        "status": {
            "required": False,
            "synonyms": [
                "status", "payment status", "transaction status", "txn status",
                "payment_status", "state"
            ],
            "excludes": ["amount", "date", "reference"]
        }
    },
    "BANK": {
        "bank_txn_id": {
            "required": True,
            "synonyms": [
                "bank transaction id", "bank txn id", "txn id", "transaction id", 
                "reference id", "bank_txn_id", "transaction_id", "chq no", "cheque number", 
                "ref no", "tran id", "journal entry", "transaction #"
            ],
            "excludes": ["order id", "invoice id", "customer id"]
        },
        "transaction_date": {
            "required": True,
            "synonyms": [
                "transaction date", "value date", "post date", "booking date", 
                "date", "txn date", "transaction_date", "clearing date", "statement date"
            ],
            "excludes": []
        },
        "amount": {
            "required": True,
            "synonyms": [
                "amount", "credit", "deposit", "transaction amount", "deposit amount", 
                "net amount", "txn amount", "credit_amount", "deposit value"
            ],
            "excludes": ["balance", "debit", "closing balance"]
        },
        "reference": {
            "required": False,
            "synonyms": [
                "reference", "description", "particulars", "narration", "remarks", 
                "ref", "order id", "ord id", "payment reference", "ref no",
                "bank reference", "bank_reference", "settlement id", "settlement_id"
            ],
            "excludes": []
        },
        "description": {
            "required": False,
            "synonyms": [
                "description", "narration", "particulars", "remarks", 
                "statement narration", "memo", "details"
            ],
            "excludes": []
        },
        "value_date": {
            "required": False,
            "synonyms": [
                "value date", "value_date", "clearing date", "settlement date",
                "effective date"
            ],
            "excludes": ["transaction date", "txn date", "statement date"]
        },
        "utr": {
            "required": False,
            "synonyms": [
                "utr", "utr number", "utr no", "unique transaction reference",
                "neft ref", "rtgs ref", "imps ref", "bank reference", "bank_reference", "settlement id", "settlement_id"
            ],
            "excludes": ["order id", "invoice id"]
        },
        "credit_amount": {
            "required": False,
            "synonyms": [
                "credit", "credit amount", "credit_amount", "deposit",
                "money in", "cr"
            ],
            "excludes": ["debit", "balance", "withdrawal"]
        },
        "debit_amount": {
            "required": False,
            "synonyms": [
                "debit", "debit amount", "debit_amount", "withdrawal",
                "money out", "dr"
            ],
            "excludes": ["credit", "balance", "deposit"]
        },
        "currency": {
            "required": False,
            "synonyms": [
                "currency", "currency code", "ccy", "curr"
            ],
            "excludes": ["amount", "total"]
        },
        "balance": {
            "required": False,
            "synonyms": [
                "balance", "closing balance", "running balance",
                "available balance", "ledger balance"
            ],
            "excludes": ["amount", "credit", "debit"]
        }
    }
}


def _clean_str(val: str) -> str:
    """Helper to sanitize and standardize column name strings for matching."""
    if not val:
        return ""
    cleaned = re.sub(r'[^a-zA-Z0-9]+', ' ', str(val)).strip().lower()
    return cleaned


class IngestionService:
    """
    Ingests and validates financial datasets into the database with idempotency.
    """

    @staticmethod
    def compute_row_hash(source_system: str, txn_date: Any, amount_raw: Any, normalized_ref: str, description: str) -> str:
        """
        Computes an invariant SHA256 hash for row-level idempotency deduplication.
        raw_row_hash = sha256(source_system + "|" + txn_date + "|" + amount_raw + "|" + normalized_ref + "|" + description)
        """
        c_sys = str(source_system).strip().upper()
        c_date = str(txn_date).strip() if txn_date is not None else ""
        c_amt = str(amount_raw).strip() if amount_raw is not None else ""
        c_ref = str(normalized_ref).strip() if normalized_ref is not None else ""
        c_desc = str(description).strip() if description is not None else ""
        raw_str = f"{c_sys}|{c_date}|{c_amt}|{c_ref}|{c_desc}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    @staticmethod
    def load_df_from_csv(file_or_path: Any) -> pd.DataFrame:
        """Loads a Pandas DataFrame from either a file path, bytes, or file-like stream."""
        if isinstance(file_or_path, str):
            if file_or_path.lower().endswith((".xlsx", ".xls")):
                return pd.read_excel(file_or_path)
            return pd.read_csv(file_or_path)
        elif isinstance(file_or_path, bytes):
            return pd.read_csv(io.BytesIO(file_or_path))
        else:
            return pd.read_csv(file_or_path)

    @staticmethod
    def parse_file(filepath: str, file_type: str) -> pd.DataFrame:
        """Parses CSV, Excel, or PDF tabular files into a clean Pandas DataFrame."""
        if file_type == "csv":
            return pd.read_csv(filepath)
        elif file_type in ["xls", "xlsx"]:
            return pd.read_excel(filepath)
        elif file_type == "pdf":
            import pdfplumber
            all_data = []
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        df = pd.DataFrame(table[1:], columns=table[0])
                        all_data.append(df)
            if all_data:
                return pd.concat(all_data, ignore_index=True)
            return pd.DataFrame()
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    @classmethod
    def get_column_previews(cls, df: pd.DataFrame, max_samples: int = 3) -> Dict[str, List[str]]:
        """
        Extracts up to max_samples non-null preview values for every column in the dataframe.
        """
        previews: Dict[str, List[str]] = {}
        for col in df.columns:
            non_null_vals = df[col].dropna().astype(str).tolist()
            cleaned_vals = [v.strip() for v in non_null_vals if v.strip()][:max_samples]
            previews[str(col)] = cleaned_vals
        return previews

    @classmethod
    def auto_map_columns(cls, df: pd.DataFrame, data_type: str) -> Dict[str, str]:
        """
        Maps source CSV headers to target canonical fields using explicit synonym lists
        and hard exclusion vetoes.
        """
        if data_type not in TARGET_SCHEMAS:
            return {}

        schema = TARGET_SCHEMAS[data_type]
        source_cols = [str(c) for c in df.columns]
        cleaned_source_cols = {col: _clean_str(col) for col in source_cols}

        # Track candidate scores: target_field -> {source_col: score}
        field_candidates: Dict[str, Dict[str, float]] = {}

        for target_field, spec in schema.items():
            field_candidates[target_field] = {}
            synonyms = [_clean_str(s) for s in spec["synonyms"]]
            excludes = [_clean_str(e) for e in spec.get("excludes", [])]

            for orig_col, clean_col in cleaned_source_cols.items():
                # 1. Hard Veto Exclusion Check
                veto = False
                for exclude_term in excludes:
                    if exclude_term and (exclude_term == clean_col or exclude_term in clean_col.split()):
                        veto = True
                        break
                if veto:
                    continue

                # 2. Exact Synonym Match
                if clean_col in synonyms:
                    field_candidates[target_field][orig_col] = 100.0
                    continue

                # 3. Fuzzy Match restricted strictly to synonym list
                best_fuzzy = 0.0
                for syn in synonyms:
                    score = fuzz.ratio(clean_col, syn)
                    if score > best_fuzzy:
                        best_fuzzy = score

                if best_fuzzy >= 85.0:
                    field_candidates[target_field][orig_col] = best_fuzzy

        # Disambiguate: assign best unique column per target field
        final_mapping: Dict[str, str] = {}
        used_cols = set()

        sorted_fields = sorted(
            field_candidates.keys(),
            key=lambda f: max(field_candidates[f].values()) if field_candidates[f] else 0.0,
            reverse=True
        )

        for field in sorted_fields:
            candidates = field_candidates[field]
            if not candidates:
                continue
            sorted_candidates = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
            for cand_col, score in sorted_candidates:
                if cand_col not in used_cols:
                    final_mapping[field] = cand_col
                    used_cols.add(cand_col)
                    break

        return final_mapping

    @classmethod
    def detect_dataset_type(cls, df: pd.DataFrame) -> Tuple[str, Dict[str, str]]:
        """
        Detects the type of financial dataset based on columns and returns suggested mapping.
        """
        scores = {}
        for d_type in ["INVOICE", "GATEWAY", "BANK"]:
            type_mapping = cls.auto_map_columns(df, d_type)
            required_fields = [f for f, s in TARGET_SCHEMAS[d_type].items() if s["required"]]
            matched_req = sum(1 for req in required_fields if req in type_mapping)
            matched_total = len(type_mapping)
            scores[d_type] = (matched_req * 3.0) + matched_total

        best_type = max(scores, key=scores.get) if max(scores.values()) > 0 else "UNKNOWN"
        suggested_mapping = cls.auto_map_columns(df, best_type) if best_type != "UNKNOWN" else {}

        return best_type, suggested_mapping

    @classmethod
    def ingest_bank_transactions(
        cls,
        db: Session,
        data_source: Any,
        run_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
    ) -> Tuple[List[BankTransaction], List[str], int, int]:
        """
        Ingests Bank transactions with idempotent SHA256 insert-or-skip deduplication.
        Returns: (records, errors, rows_ingested, rows_skipped)
        """
        df = cls.load_df_from_csv(data_source) if not isinstance(data_source, pd.DataFrame) else data_source
        errors = []
        
        required = ["bank_txn_id", "transaction_date", "amount"]
        missing = set(required) - set(df.columns)
        if missing:
            raise ValueError(f"Bank data missing required columns: {missing}")

        existing_hashes = set(
            h[0] for h in db.query(BankTransaction.raw_row_hash)
            .filter(BankTransaction.raw_row_hash.isnot(None))
            .all()
        )

        records = []
        rows_ingested = 0
        rows_skipped = 0

        for idx, row in df.iterrows():
            try:
                raw_b_id = str(row["bank_txn_id"]).strip()
                b_id = f"{dataset_id[:8]}_{raw_b_id}" if dataset_id else raw_b_id
                t_date = NormalizationService.normalize_date(row["transaction_date"])
                raw_amt = row["amount"]
                norm_amt = NormalizationService.normalize_amount(raw_amt)
                
                t_type = str(row.get("transaction_type", "CREDIT")).upper()
                
                # Handle separate credit/debit columns
                credit_amt_raw = row.get("credit_amount") if "credit_amount" in row else None
                debit_amt_raw = row.get("debit_amount")
                credit_amt = NormalizationService.normalize_amount(credit_amt_raw) if credit_amt_raw is not None and pd.notnull(credit_amt_raw) and str(credit_amt_raw).strip() else None
                debit_amt = NormalizationService.normalize_amount(debit_amt_raw) if debit_amt_raw is not None and pd.notnull(debit_amt_raw) and str(debit_amt_raw).strip() else None
                
                if norm_amt == 0.0 and credit_amt and credit_amt > 0:
                    norm_amt = credit_amt
                    t_type = "CREDIT"
                elif norm_amt == 0.0 and debit_amt and debit_amt > 0:
                    norm_amt = debit_amt
                    t_type = "DEBIT"
                        
                desc = str(row.get("description", row.get("narration", "")))
                ref = str(row.get("reference", row.get("bank_reference", row.get("settlement_id", ""))))
                if not ref or not ref.strip():
                    ref = str(row.get("bank_reference", row.get("settlement_id", desc or raw_b_id)))

                norm_ref = NormalizationService.normalize_reference(ref)
                norm_desc = NormalizationService.normalize_description(desc)

                # Extended fields
                value_date_raw = row.get("value_date")
                v_date = NormalizationService.normalize_date(value_date_raw) if value_date_raw is not None and pd.notnull(value_date_raw) and str(value_date_raw).strip() else None
                utr_raw = row.get("utr", row.get("bank_reference", row.get("settlement_id", "")))
                utr_val = str(utr_raw).strip() if utr_raw is not None and pd.notnull(utr_raw) and str(utr_raw).strip() else None
                currency_val = str(row.get("currency", "INR")).strip().upper() if "currency" in row and pd.notnull(row.get("currency")) else "INR"
                balance_raw = row.get("balance")
                balance_val = NormalizationService.normalize_amount(balance_raw) if balance_raw is not None and pd.notnull(balance_raw) and str(balance_raw).strip() else None

                row_hash = cls.compute_row_hash("BANK", t_date, norm_amt, norm_ref, norm_desc)

                if row_hash in existing_hashes:
                    rows_skipped += 1
                    continue

                record = BankTransaction(
                    bank_txn_id=b_id,
                    run_id=run_id,
                    dataset_id=dataset_id,
                    transaction_date=t_date,
                    amount=norm_amt,
                    description=desc,
                    reference=ref,
                    transaction_type=t_type,
                    normalized_amount=norm_amt,
                    normalized_date=t_date,
                    normalized_ref=norm_ref,
                    normalized_desc=norm_desc,
                    value_date=v_date,
                    utr=utr_val,
                    credit_amount=credit_amt,
                    debit_amount=debit_amt,
                    currency=currency_val,
                    balance=balance_val,
                    raw_row_hash=row_hash,
                )
                db.merge(record)
                records.append(record)
                existing_hashes.add(row_hash)
                rows_ingested += 1
            except Exception as e:
                errors.append(f"Bank row {idx} error: {str(e)}")

        return records, errors, rows_ingested, rows_skipped

    @classmethod
    def ingest_gateway_transactions(
        cls,
        db: Session,
        data_source: Any,
        run_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
    ) -> Tuple[List[GatewayTransaction], List[str], int, int]:
        """
        Ingests Gateway transactions with gross/net decomposition and idempotent hash deduplication.
        Returns: (records, errors, rows_ingested, rows_skipped)
        """
        df = cls.load_df_from_csv(data_source) if not isinstance(data_source, pd.DataFrame) else data_source
        errors = []

        required = ["gateway_txn_id", "transaction_date"]
        missing = set(required) - set(df.columns)
        if missing or not ("amount" in df.columns or "gross_amount" in df.columns):
            raise ValueError(f"Gateway data missing required columns: {missing or 'amount/gross_amount'}")

        existing_hashes = set(
            h[0] for h in db.query(GatewayTransaction.raw_row_hash)
            .filter(GatewayTransaction.raw_row_hash.isnot(None))
            .all()
        )

        records = []
        rows_ingested = 0
        rows_skipped = 0

        for idx, row in df.iterrows():
            try:
                raw_g_id = str(row["gateway_txn_id"]).strip()
                g_id = f"{dataset_id[:8]}_{raw_g_id}" if dataset_id else raw_g_id
                t_date = NormalizationService.normalize_date(row["transaction_date"])
                
                raw_amt = row.get("gross_amount", row.get("amount", 0.0))
                gross_amt = NormalizationService.normalize_amount(raw_amt)
                
                gateway_fee = NormalizationService.normalize_amount(row.get("gateway_fee", row.get("fee", 0.0)))
                tax_on_fee = NormalizationService.normalize_amount(row.get("tax_on_fee", row.get("gst_on_fee", 0.0)))
                
                net_derived = False
                raw_net = row.get("net_amount", row.get("net_settlement", row.get("settlement_amount")))
                if raw_net is not None and not pd.isna(raw_net) and str(raw_net).strip():
                    net_amt = NormalizationService.normalize_amount(raw_net)
                else:
                    net_amt = gross_amt - gateway_fee - tax_on_fee
                    net_derived = True

                cust = str(row.get("customer_name", ""))
                ref = str(row.get("payment_reference", row.get("order_id", row.get("invoice_id", ""))))
                if not ref or not ref.strip():
                    ref = str(row.get("invoice_id", row.get("order_id", raw_g_id)))
                status = str(row.get("status", "CAPTURED")).upper()

                # Extended canonical fields
                gw_order_id = str(row["gateway_order_id"]).strip() if "gateway_order_id" in row and pd.notnull(row["gateway_order_id"]) else (
                    str(row["order_id"]).strip() if "order_id" in row and pd.notnull(row["order_id"]) else (
                        str(row["invoice_id"]).strip() if "invoice_id" in row and pd.notnull(row["invoice_id"]) else (
                            str(row["settlement_id"]).strip() if "settlement_id" in row and pd.notnull(row["settlement_id"]) else None
                        )
                    )
                )
                pay_method = str(row["payment_method"]).strip().upper() if "payment_method" in row and pd.notnull(row["payment_method"]) else None
                curr_val = str(row.get("currency", "INR")).strip().upper() if "currency" in row and pd.notnull(row.get("currency")) else "INR"
                gw_name = str(row.get("gateway_name", row.get("gateway", ""))).strip().lower() if ("gateway_name" in row or "gateway" in row) and pd.notnull(row.get("gateway_name", row.get("gateway"))) else None

                norm_ref = NormalizationService.normalize_reference(ref)
                norm_cust = NormalizationService.normalize_customer_name(cust)

                row_hash = cls.compute_row_hash("GATEWAY", t_date, gross_amt, norm_ref, norm_cust)

                if row_hash in existing_hashes:
                    rows_skipped += 1
                    continue

                record = GatewayTransaction(
                    gateway_txn_id=g_id,
                    run_id=run_id,
                    dataset_id=dataset_id,
                    transaction_date=t_date,
                    amount=gross_amt,
                    gross_amount=gross_amt,
                    net_amount=net_amt,
                    net_amount_derived=net_derived,
                    gateway_fee=gateway_fee,
                    tax_on_fee=tax_on_fee,
                    net_settlement=net_amt,
                    customer_name=cust,
                    payment_reference=ref,
                    status=status,
                    gateway_order_id=gw_order_id,
                    payment_method=pay_method,
                    currency=curr_val,
                    gateway_name=gw_name,
                    normalized_amount=gross_amt,
                    normalized_date=t_date,
                    normalized_ref=norm_ref,
                    normalized_customer=norm_cust,
                    raw_row_hash=row_hash,
                )
                db.merge(record)
                records.append(record)
                existing_hashes.add(row_hash)
                rows_ingested += 1
            except Exception as e:
                errors.append(f"Gateway row {idx} error: {str(e)}")

        return records, errors, rows_ingested, rows_skipped

    @classmethod
    def ingest_invoices(
        cls,
        db: Session,
        data_source: Any,
        run_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
    ) -> Tuple[List[Invoice], List[str], int, int]:
        """
        Ingests Invoice records with idempotent SHA256 insert-or-skip deduplication.
        Returns: (records, errors, rows_ingested, rows_skipped)
        """
        df = cls.load_df_from_csv(data_source) if not isinstance(data_source, pd.DataFrame) else data_source
        errors = []

        required = ["invoice_id", "invoice_date", "amount"]
        missing = set(required) - set(df.columns)
        if missing:
            raise ValueError(f"Invoice data missing required columns: {missing}")

        existing_hashes = set(
            h[0] for h in db.query(Invoice.raw_row_hash)
            .filter(Invoice.raw_row_hash.isnot(None))
            .all()
        )

        records = []
        rows_ingested = 0
        rows_skipped = 0

        for idx, row in df.iterrows():
            try:
                raw_i_id = str(row["invoice_id"]).strip()
                i_id = f"{dataset_id[:8]}_{raw_i_id}" if dataset_id else raw_i_id
                t_date = NormalizationService.normalize_date(row["invoice_date"])
                raw_amt = row["amount"]
                norm_amt = NormalizationService.normalize_amount(raw_amt)
                cust = str(row.get("customer_name", ""))
                ref = str(row.get("invoice_reference", row.get("order_id", "")))
                if not ref or not ref.strip():
                    ref = raw_i_id
                status = str(row.get("status", "ISSUED")).upper()

                # Extended canonical fields
                order_id_val = str(row["order_id"]).strip() if "order_id" in row and pd.notnull(row["order_id"]) else None
                cust_id_val = str(row["customer_id"]).strip() if "customer_id" in row and pd.notnull(row["customer_id"]) else None
                cust_email_val = str(row["customer_email"]).strip() if "customer_email" in row and pd.notnull(row["customer_email"]) else None
                tax_raw = row.get("tax_amount")
                tax_val = NormalizationService.normalize_amount(tax_raw) if tax_raw is not None and pd.notnull(tax_raw) and str(tax_raw).strip() else None
                curr_val = str(row.get("currency", "INR")).strip().upper() if "currency" in row and pd.notnull(row.get("currency")) else "INR"
                due_raw = row.get("due_date")
                due_val = NormalizationService.normalize_date(due_raw) if due_raw is not None and pd.notnull(due_raw) and str(due_raw).strip() else None

                norm_ref = NormalizationService.normalize_reference(ref)
                norm_cust = NormalizationService.normalize_customer_name(cust)

                row_hash = cls.compute_row_hash("INVOICE", t_date, norm_amt, norm_ref, norm_cust)

                if row_hash in existing_hashes:
                    rows_skipped += 1
                    continue

                record = Invoice(
                    invoice_id=i_id,
                    run_id=run_id,
                    dataset_id=dataset_id,
                    invoice_date=t_date,
                    customer_name=cust,
                    amount=norm_amt,
                    invoice_reference=ref,
                    status=status,
                    order_id=order_id_val,
                    customer_id=cust_id_val,
                    customer_email=cust_email_val,
                    tax_amount=tax_val,
                    currency=curr_val,
                    due_date=due_val,
                    normalized_amount=norm_amt,
                    normalized_date=t_date,
                    normalized_ref=norm_ref,
                    normalized_customer=norm_cust,
                    raw_row_hash=row_hash,
                )
                db.merge(record)
                records.append(record)
                existing_hashes.add(row_hash)
                rows_ingested += 1
            except Exception as e:
                errors.append(f"Invoice row {idx} error: {str(e)}")

        return records, errors, rows_ingested, rows_skipped

