"""
Duplicate Transaction Detection Service.

Problem Solved:
Identifies internal duplicate entries within the same financial data source (Bank, Gateway, Invoices)
arising from accidental re-uploads, network retry loops, or gateway double-captures.

Why It Exists:
To prevent double accounting and detect duplicate liabilities before ledger posting,
flagging collisions with deterministic evidence chains.

Input:
List of transaction entities from a single source type (BANK, GATEWAY, INVOICE).

Output:
List of detected duplicate groups with primary and duplicate records, group IDs, and evidence JSON.
"""

import uuid
from typing import Dict, Any, List, Optional
from app.services.reconciliation.evidence import EvidenceBuilder


class DuplicateDetector:
    """
    Scans a set of financial records from a single source for internal duplicate collisions.
    """

    @classmethod
    def detect_duplicates(
        cls,
        records: List[Any],
        source_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Detects duplicate records based on raw row hash or identical (amount, date, reference/description).

        Args:
            records: List of transaction ORM models or dictionaries.
            source_type: Source identifier ('BANK', 'GATEWAY', 'INVOICE').

        Returns:
            List of dictionary structures for each duplicate group found:
            - duplicate_group_id: Unique string identifier for the duplicate group.
            - source_type: The source dataset type.
            - primary_record: The first detected record in the group.
            - duplicate_records: List of subsequent duplicate records.
            - count: Total number of records in the group.
            - evidence_json: Structured evidence JSON string.
        """
        if not records or len(records) < 2:
            return []

        # Group records by fingerprint or raw_row_hash
        groups_by_key: Dict[str, List[Any]] = {}

        for rec in records:
            # Check for raw_row_hash first if present
            raw_hash = getattr(rec, "raw_row_hash", None)
            if raw_hash and str(raw_hash).strip():
                key = f"hash:{str(raw_hash).strip()}"
            else:
                # Fallback to normalized/raw amount, date, reference
                amt = float(getattr(rec, "normalized_amount", getattr(rec, "amount", 0.0)))
                dt = str(getattr(rec, "normalized_date", getattr(rec, "transaction_date", getattr(rec, "invoice_date", ""))))
                ref = getattr(
                    rec,
                    "normalized_ref",
                    getattr(
                        rec,
                        "reference",
                        getattr(rec, "payment_reference", getattr(rec, "invoice_reference", getattr(rec, "description", "")))
                    )
                )
                key = f"tuple:{round(amt, 2)}|{dt}|{str(ref).strip().lower()}"

            groups_by_key.setdefault(key, []).append(rec)

        duplicate_groups: List[Dict[str, Any]] = []

        for key, rec_list in groups_by_key.items():
            if len(rec_list) > 1:
                group_id = f"DUP_{source_type.upper()}_{uuid.uuid4().hex[:8].upper()}"
                primary = rec_list[0]
                duplicates = rec_list[1:]

                primary_id = getattr(
                    primary,
                    "bank_txn_id",
                    getattr(primary, "gateway_txn_id", getattr(primary, "invoice_id", None)),
                )
                dup_ids = [
                    getattr(r, "bank_txn_id", getattr(r, "gateway_txn_id", getattr(r, "invoice_id", None)))
                    for r in duplicates
                ]

                amt = float(getattr(primary, "amount", 0.0))
                dt_val = str(getattr(primary, "transaction_date", getattr(primary, "invoice_date", "")))
                ref_val = str(getattr(primary, "reference", getattr(primary, "payment_reference", getattr(primary, "invoice_reference", ""))))

                evidence_json = EvidenceBuilder.build_exception_evidence(
                    exception_type="DUPLICATE_TRANSACTION",
                    reason=(
                        f"Duplicate transaction collision in {source_type}: {len(rec_list)} records "
                        f"share identical fingerprint ({key})."
                    ),
                    amounts={
                        "unit_amount": amt,
                        "total_duplicated_amount": round(amt * len(duplicates), 2),
                        "total_group_volume": round(amt * len(rec_list), 2),
                    },
                    dates={
                        "transaction_date": dt_val,
                    },
                    references={
                        "reference": ref_val,
                        "primary_id": primary_id,
                        "duplicate_ids": dup_ids,
                    },
                    policy_citation="Anti-Double-Billing Framework & Internal Control Standard 6.1 (Idempotency Audit)",
                    extra_data={
                        "source_type": source_type,
                        "duplicate_group_id": group_id,
                        "fingerprint_key": key,
                        "duplicate_count": len(duplicates),
                    },
                )

                duplicate_groups.append({
                    "duplicate_group_id": group_id,
                    "source_type": source_type,
                    "primary_record": primary,
                    "duplicate_records": duplicates,
                    "count": len(rec_list),
                    "fingerprint": key,
                    "evidence_json": evidence_json,
                })

        return duplicate_groups
