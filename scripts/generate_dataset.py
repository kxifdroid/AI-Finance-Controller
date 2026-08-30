#!/usr/bin/env python3
"""
Synthetic Financial Dataset Generator with Controlled Realistic Noise.

Problem Solved:
Generates realistic 3-way financial reconciliation datasets (Bank Statements,
Payment Gateway Logs, ERP Invoices) along with an isolated Ground Truth benchmark.

Features Generated:
- Many-to-one batch settlements (e.g. 1 bank deposit for 2-4 gateway transactions)
- Gateway fee + GST decomposition (gross, fee, tax_on_fee, net_settlement)
- Duplicate transactions with collisions (cross-source and intra-source)
- UTR and Order IDs linked consistently across files
- Rich canonical columns for Bank, Gateway, and Invoice records
- Clean ground_truth.json reflecting the expanded exception taxonomy

Output Files:
- data/generated/bank_transactions.csv
- data/generated/gateway_transactions.csv
- data/generated/invoices.csv
- data/ground_truth/ground_truth.json
"""

import os
import sys
import json
import random
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd


# Real-world Indian / Global enterprise business names & noise variants
COMPANY_NAMES = [
    ("Acme Technologies", ["Acme Tech Pvt Ltd", "Acme Technologies LLC", "ACME TECH", "Acme Technologies Inc."]),
    ("Nexus Retail Solutions", ["Nexus Retail Pvt. Ltd.", "NEXUS RETAIL", "Nexus Retail Solutions India", "Nexus Retail"]),
    ("Apex Global Logistics", ["Apex Logistics Ltd", "APEX GLOBAL LOGISTICS", "Apex Global", "Apex Logistics"]),
    ("Zenith Financial Services", ["Zenith Financial Pvt Ltd", "ZENITH FINANCIAL", "Zenith Fin Serv", "Zenith Financial"]),
    ("Quantum Cloud Systems", ["Quantum Cloud Systems India", "QUANTUM CLOUD", "Quantum Cloud Pvt Ltd", "Quantum Cloud"]),
    ("Starlight Media Works", ["Starlight Media Pvt. Ltd.", "STARLIGHT MEDIA", "Starlight Media Works Inc", "Starlight Media"]),
    ("Vortex Manufacturing", ["Vortex Mfg Pvt Ltd", "VORTEX MFG", "Vortex Manufacturing Co.", "Vortex Mfg"]),
    ("Horizon Healthcare", ["Horizon Health Services Ltd", "HORIZON HEALTHCARE", "Horizon Health Pvt Ltd", "Horizon Health"]),
    ("Solaris Energy Corp", ["Solaris Energy Solutions", "SOLARIS ENERGY", "Solaris Energy Corp Ltd", "Solaris Energy"]),
    ("Paramount Consulting Group", ["Paramount Consulting Pvt Ltd", "PARAMOUNT CONSULTING", "Paramount Consult", "Paramount Consulting"]),
    ("Pinnacle Food Products", ["Pinnacle Foods Ltd", "PINNACLE FOODS", "Pinnacle Food Products Pvt Ltd", "Pinnacle Foods"]),
    ("Titanium Infrastructure", ["Titanium Infra Ltd", "TITANIUM INFRA", "Titanium Infrastructure Co", "Titanium Infra"]),
    ("BlueWave Maritime", ["BlueWave Maritime Services", "BLUEWAVE MARITIME", "BlueWave Maritime Pvt Ltd", "BlueWave"]),
    ("Summit Telecom", ["Summit Telecommunications Ltd", "SUMMIT TELECOM", "Summit Telecom India", "Summit Telecom"]),
    ("Omni Retail Ventures", ["Omni Retail Pvt Ltd", "OMNI RETAIL", "Omni Retail Ventures LLC", "Omni Retail"]),
    ("Aegis Security Solutions", ["Aegis Security Systems Ltd", "AEGIS SECURITY", "Aegis Security Pvt Ltd", "Aegis Security"]),
    ("Crestview Real Estate", ["Crestview Properties Ltd", "CRESTVIEW REAL ESTATE", "Crestview Realty Pvt Ltd", "Crestview Realty"]),
    ("Metro Mobility Cabs", ["Metro Mobility Services", "METRO MOBILITY", "Metro Mobility Pvt Ltd", "Metro Cabs"]),
    ("Silverline Chemicals", ["Silverline Chem Industries", "SILVERLINE CHEMICALS", "Silverline Chem Ltd", "Silverline Chem"]),
    ("Innovate Digital Labs", ["Innovate Labs Pvt Ltd", "INNOVATE DIGITAL", "Innovate Digital Labs LLC", "Innovate Digital"]),
]

PAYMENT_METHODS = ["UPI", "CARD", "NET_BANKING", "WALLET"]
GATEWAYS = ["razorpay", "stripe", "paytm", "hdfc_smartgateway"]


def generate_synthetic_data(count: int = 250, seed: int = 42, output_dir: str = "data"):
    """
    Generates synthetic bank, gateway, and invoice datasets with controlled noise and ground truth.
    """
    random.seed(seed)
    base_date = datetime(2026, 8, 1)

    # Output paths
    gen_dir = os.path.join(output_dir, "generated")
    gt_dir = os.path.join(output_dir, "ground_truth")
    os.makedirs(gen_dir, exist_ok=True)
    os.makedirs(gt_dir, exist_ok=True)

    bank_records = []
    gateway_records = []
    invoice_records = []
    ground_truth_records = []

    # Distribution breakdown
    n_many_to_one = max(4, int(count * 0.15))
    n_exact = max(10, int(count * 0.45))
    n_ambiguous = max(4, int(count * 0.10))
    n_fee_mismatch = max(3, int(count * 0.05))
    n_duplicates = max(3, int(count * 0.05))
    n_missing = max(3, int(count * 0.05))
    n_edge_cases = max(3, count - (n_many_to_one + n_exact + n_ambiguous + n_fee_mismatch + n_duplicates + n_missing))

    current_idx = 1

    def fmt_id(prefix: str, num: int) -> str:
        return f"{prefix}{num:05d}"

    def rand_amount() -> float:
        tier = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
        if tier == 1:
            return round(random.uniform(500.0, 15000.0), 2)
        elif tier == 2:
            return round(random.uniform(15000.0, 100000.0), 2)
        else:
            return round(random.uniform(100000.0, 500000.0), 2)

    def compute_fee_decomp(gross: float, rate: float = 0.02, gst_rate: float = 0.18):
        fee = round(gross * rate, 2)
        tax = round(fee * gst_rate, 2)
        net = round(gross - fee - tax, 2)
        return fee, tax, net

    # =========================================================================
    # 1. Exact Matches with Full Fee Decomposition (~45%)
    # =========================================================================
    for _ in range(n_exact):
        idx_str = fmt_id("TXN", current_idx)
        b_id = f"BNK_{idx_str}"
        g_id = f"GW_{idx_str}"
        i_id = f"INV_{idx_str}"
        ord_id = f"ORD_{random.randint(100000, 999999)}"
        utr_num = f"UTR{random.randint(1000000000, 9999999999)}"
        cust_id = f"CUST_{random.randint(1000, 9999)}"

        company_tuple = random.choice(COMPANY_NAMES)
        canonical_name = company_tuple[0]
        ref_num = f"{random.randint(100000, 999999)}"
        gross_amount = rand_amount()
        fee, tax, net_settlement = compute_fee_decomp(gross_amount)

        day_offset = random.randint(0, 20)
        inv_date = base_date + timedelta(days=day_offset)
        gw_date = inv_date + timedelta(days=random.choice([0, 1]))
        bank_date = gw_date + timedelta(days=random.choice([0, 1]))

        # Invoice record
        invoice_records.append({
            "invoice_id": i_id,
            "order_id": ord_id,
            "invoice_date": inv_date.strftime("%Y-%m-%d"),
            "due_date": (inv_date + timedelta(days=30)).strftime("%Y-%m-%d"),
            "customer_name": canonical_name,
            "customer_id": cust_id,
            "customer_email": f"billing@{canonical_name.lower().replace(' ', '')}.com",
            "amount": gross_amount,
            "tax_amount": round(gross_amount * 0.18, 2),
            "currency": "INR",
            "invoice_reference": f"INV-{ref_num}",
            "status": "PAID"
        })

        # Gateway record with full fee decomposition
        gateway_records.append({
            "gateway_txn_id": g_id,
            "gateway_order_id": ord_id,
            "order_id": ord_id,
            "transaction_date": gw_date.strftime("%Y-%m-%d"),
            "amount": gross_amount,
            "gross_amount": gross_amount,
            "gateway_fee": fee,
            "tax_on_fee": tax,
            "net_settlement": net_settlement,
            "customer_name": canonical_name,
            "payment_reference": f"PAY-{ref_num}",
            "payment_method": random.choice(PAYMENT_METHODS),
            "gateway_name": random.choice(GATEWAYS),
            "currency": "INR",
            "status": "CAPTURED"
        })

        # Bank record receiving net settlement (or gross credit)
        bank_records.append({
            "bank_txn_id": b_id,
            "transaction_date": bank_date.strftime("%Y-%m-%d"),
            "value_date": bank_date.strftime("%Y-%m-%d"),
            "amount": net_settlement,
            "credit_amount": net_settlement,
            "debit_amount": 0.0,
            "description": f"NEFT CR - {canonical_name.upper()} - REF {ref_num} UTR {utr_num}",
            "reference": f"REF-{ref_num}",
            "utr": utr_num,
            "transaction_type": "CREDIT",
            "currency": "INR",
            "balance": round(random.uniform(500000.0, 5000000.0), 2)
        })

        ground_truth_records.append({
            "bank_txn_id": b_id,
            "gateway_txn_id": g_id,
            "invoice_id": i_id,
            "order_id": ord_id,
            "expected_status": "MATCH",
            "expected_risk": "LOW",
            "amount": gross_amount,
            "discrepancy_reason": None,
            "exception_type": None
        })

        current_idx += 1

    # =========================================================================
    # 2. Many-to-One Batch Settlements (~15%)
    # 1 Bank Deposit for 2 to 4 Gateway Transactions
    # =========================================================================
    batch_counter = 1
    items_created = 0
    while items_created < n_many_to_one:
        group_size = random.choice([2, 3, 4])
        batch_idx_str = f"BATCH{batch_counter:03d}"
        batch_bank_id = f"BNK_BATCH_{batch_idx_str}"
        batch_ref = f"{random.randint(100000, 999999)}"
        batch_utr = f"UTR{random.randint(1000000000, 9999999999)}"

        day_offset = random.randint(1, 20)
        batch_date = base_date + timedelta(days=day_offset)
        bank_payout_date = batch_date + timedelta(days=1)

        batch_gross_sum = 0.0
        batch_fee_sum = 0.0
        batch_tax_sum = 0.0
        batch_net_sum = 0.0

        batch_gw_ids = []
        batch_inv_ids = []

        for item_i in range(group_size):
            item_idx_str = fmt_id("TXN", current_idx)
            g_id = f"GW_{item_idx_str}"
            i_id = f"INV_{item_idx_str}"
            ord_id = f"ORD_{random.randint(100000, 999999)}"
            ref_num = f"{random.randint(100000, 999999)}"
            cust_id = f"CUST_{random.randint(1000, 9999)}"

            company_tuple = random.choice(COMPANY_NAMES)
            canonical_name = company_tuple[0]
            gross_amount = round(random.uniform(1000.0, 10000.0), 2)
            fee, tax, net_settlement = compute_fee_decomp(gross_amount)

            batch_gross_sum += gross_amount
            batch_fee_sum += fee
            batch_tax_sum += tax
            batch_net_sum += net_settlement

            batch_gw_ids.append(g_id)
            batch_inv_ids.append(i_id)

            invoice_records.append({
                "invoice_id": i_id,
                "order_id": ord_id,
                "invoice_date": batch_date.strftime("%Y-%m-%d"),
                "due_date": (batch_date + timedelta(days=30)).strftime("%Y-%m-%d"),
                "customer_name": canonical_name,
                "customer_id": cust_id,
                "customer_email": f"accounts@{canonical_name.lower().replace(' ', '')}.com",
                "amount": gross_amount,
                "tax_amount": round(gross_amount * 0.18, 2),
                "currency": "INR",
                "invoice_reference": f"INV-{ref_num}",
                "status": "PAID"
            })

            gateway_records.append({
                "gateway_txn_id": g_id,
                "gateway_order_id": ord_id,
                "order_id": ord_id,
                "transaction_date": batch_date.strftime("%Y-%m-%d"),
                "amount": gross_amount,
                "gross_amount": gross_amount,
                "gateway_fee": fee,
                "tax_on_fee": tax,
                "net_settlement": net_settlement,
                "customer_name": canonical_name,
                "payment_reference": f"PAY-{ref_num}",
                "payment_method": random.choice(PAYMENT_METHODS),
                "gateway_name": "razorpay",
                "currency": "INR",
                "status": "CAPTURED"
            })

            ground_truth_records.append({
                "bank_txn_id": batch_bank_id,
                "gateway_txn_id": g_id,
                "invoice_id": i_id,
                "order_id": ord_id,
                "expected_status": "MATCH",
                "expected_risk": "LOW",
                "amount": gross_amount,
                "discrepancy_reason": f"Part of many-to-one batch payout ({group_size} transactions aggregated in bank deposit)",
                "exception_type": "MANY_TO_ONE_SETTLEMENT"
            })

            current_idx += 1
            items_created += 1

        batch_net_sum = round(batch_net_sum, 2)
        batch_gross_sum = round(batch_gross_sum, 2)

        # Single aggregate bank deposit for all gateway transactions in the batch
        bank_records.append({
            "bank_txn_id": batch_bank_id,
            "transaction_date": bank_payout_date.strftime("%Y-%m-%d"),
            "value_date": bank_payout_date.strftime("%Y-%m-%d"),
            "amount": batch_net_sum,
            "credit_amount": batch_net_sum,
            "debit_amount": 0.0,
            "description": f"RAZORPAY PAYOUT BATCH - {group_size} TXNS - REF {batch_ref} UTR {batch_utr}",
            "reference": f"BATCH-{batch_ref}",
            "utr": batch_utr,
            "transaction_type": "CREDIT",
            "currency": "INR",
            "balance": round(random.uniform(1000000.0, 8000000.0), 2)
        })

        batch_counter += 1

    # =========================================================================
    # 3. Ambiguous Matches (~10%)
    # Name variations, formatting shifts, 2-3 day lag
    # =========================================================================
    for _ in range(n_ambiguous):
        idx_str = fmt_id("TXN", current_idx)
        b_id = f"BNK_{idx_str}"
        g_id = f"GW_{idx_str}"
        i_id = f"INV_{idx_str}"
        ord_id = f"ORD_{random.randint(100000, 999999)}"
        utr_num = f"UTR{random.randint(1000000000, 9999999999)}"

        company_tuple = random.choice(COMPANY_NAMES)
        canonical_name = company_tuple[0]
        var_name_gw = random.choice(company_tuple[1])
        var_name_bank = random.choice(company_tuple[1])
        ref_num = f"{random.randint(100000, 999999)}"
        gross_amount = rand_amount()
        fee, tax, net_settlement = compute_fee_decomp(gross_amount)

        day_offset = random.randint(0, 20)
        inv_date = base_date + timedelta(days=day_offset)
        gw_date = inv_date + timedelta(days=random.randint(1, 2))
        bank_date = gw_date + timedelta(days=random.randint(1, 3))

        invoice_records.append({
            "invoice_id": i_id,
            "order_id": ord_id,
            "invoice_date": inv_date.strftime("%Y-%m-%d"),
            "due_date": (inv_date + timedelta(days=30)).strftime("%Y-%m-%d"),
            "customer_name": canonical_name,
            "customer_id": f"CUST_{random.randint(1000, 9999)}",
            "customer_email": f"finance@{canonical_name.lower().replace(' ', '')}.com",
            "amount": gross_amount,
            "tax_amount": round(gross_amount * 0.18, 2),
            "currency": "INR",
            "invoice_reference": f"INV/{ref_num}",
            "status": "PAID"
        })

        gateway_records.append({
            "gateway_txn_id": g_id,
            "gateway_order_id": ord_id,
            "order_id": ord_id,
            "transaction_date": gw_date.strftime("%Y-%m-%d"),
            "amount": gross_amount,
            "gross_amount": gross_amount,
            "gateway_fee": fee,
            "tax_on_fee": tax,
            "net_settlement": net_settlement,
            "customer_name": var_name_gw,
            "payment_reference": f"PG_{ref_num}",
            "payment_method": random.choice(PAYMENT_METHODS),
            "gateway_name": random.choice(GATEWAYS),
            "currency": "INR",
            "status": "CAPTURED"
        })

        bank_records.append({
            "bank_txn_id": b_id,
            "transaction_date": bank_date.strftime("%Y-%m-%d"),
            "value_date": bank_date.strftime("%Y-%m-%d"),
            "amount": net_settlement,
            "credit_amount": net_settlement,
            "debit_amount": 0.0,
            "description": f"UPI/CMS SETTLEMENT - {var_name_bank} - {ref_num} UTR {utr_num}",
            "reference": ref_num,
            "utr": utr_num,
            "transaction_type": "CREDIT",
            "currency": "INR",
            "balance": round(random.uniform(500000.0, 5000000.0), 2)
        })

        ground_truth_records.append({
            "bank_txn_id": b_id,
            "gateway_txn_id": g_id,
            "invoice_id": i_id,
            "order_id": ord_id,
            "expected_status": "MATCH",
            "expected_risk": "LOW",
            "amount": gross_amount,
            "discrepancy_reason": "Entity name formatting variation & T+2 settlement lag",
            "exception_type": None
        })

        current_idx += 1

    # =========================================================================
    # 4. Fee Mismatch Exceptions (~5%)
    # Excessive fee deduction or unexplained variance
    # =========================================================================
    for _ in range(n_fee_mismatch):
        idx_str = fmt_id("TXN", current_idx)
        b_id = f"BNK_{idx_str}"
        g_id = f"GW_{idx_str}"
        i_id = f"INV_{idx_str}"
        ord_id = f"ORD_{random.randint(100000, 999999)}"
        utr_num = f"UTR{random.randint(1000000000, 9999999999)}"

        company_tuple = random.choice(COMPANY_NAMES)
        canonical_name = company_tuple[0]
        ref_num = f"{random.randint(100000, 999999)}"
        gross_amount = rand_amount()
        fee, tax, expected_net = compute_fee_decomp(gross_amount)

        # Injected excessive deduction (e.g. 10% fee mismatch)
        actual_bank_credit = round(gross_amount * 0.90, 2)
        unexplained_delta = round(expected_net - actual_bank_credit, 2)

        day_offset = random.randint(0, 20)
        inv_date = base_date + timedelta(days=day_offset)
        gw_date = inv_date + timedelta(days=1)
        bank_date = gw_date + timedelta(days=1)

        invoice_records.append({
            "invoice_id": i_id,
            "order_id": ord_id,
            "invoice_date": inv_date.strftime("%Y-%m-%d"),
            "due_date": (inv_date + timedelta(days=30)).strftime("%Y-%m-%d"),
            "customer_name": canonical_name,
            "customer_id": f"CUST_{random.randint(1000, 9999)}",
            "customer_email": f"finance@{canonical_name.lower().replace(' ', '')}.com",
            "amount": gross_amount,
            "tax_amount": round(gross_amount * 0.18, 2),
            "currency": "INR",
            "invoice_reference": f"INV-{ref_num}",
            "status": "PAID"
        })

        gateway_records.append({
            "gateway_txn_id": g_id,
            "gateway_order_id": ord_id,
            "order_id": ord_id,
            "transaction_date": gw_date.strftime("%Y-%m-%d"),
            "amount": gross_amount,
            "gross_amount": gross_amount,
            "gateway_fee": fee,
            "tax_on_fee": tax,
            "net_settlement": expected_net,
            "customer_name": canonical_name,
            "payment_reference": f"PAY-{ref_num}",
            "payment_method": random.choice(PAYMENT_METHODS),
            "gateway_name": "razorpay",
            "currency": "INR",
            "status": "CAPTURED"
        })

        bank_records.append({
            "bank_txn_id": b_id,
            "transaction_date": bank_date.strftime("%Y-%m-%d"),
            "value_date": bank_date.strftime("%Y-%m-%d"),
            "amount": actual_bank_credit,
            "credit_amount": actual_bank_credit,
            "debit_amount": 0.0,
            "description": f"NEFT CR - {canonical_name.upper()} - REF {ref_num} UTR {utr_num}",
            "reference": f"REF-{ref_num}",
            "utr": utr_num,
            "transaction_type": "CREDIT",
            "currency": "INR",
            "balance": round(random.uniform(500000.0, 5000000.0), 2)
        })

        ground_truth_records.append({
            "bank_txn_id": b_id,
            "gateway_txn_id": g_id,
            "invoice_id": i_id,
            "order_id": ord_id,
            "expected_status": "EXCEPTION",
            "expected_risk": "HIGH",
            "amount": gross_amount,
            "discrepancy_reason": f"Excessive fee deduction: Bank credited ₹{actual_bank_credit:,.2f} vs expected net ₹{expected_net:,.2f} (delta: ₹{unexplained_delta:,.2f})",
            "exception_type": "FEE_MISMATCH"
        })

        current_idx += 1

    # =========================================================================
    # 5. Duplicate Transactions with Collisions (~5%)
    # Cross-source / Intra-source double charge collisions
    # =========================================================================
    for _ in range(n_duplicates):
        idx_str = fmt_id("TXN", current_idx)
        b_id1 = f"BNK_{idx_str}_A"
        b_id2 = f"BNK_{idx_str}_B"
        g_id1 = f"GW_{idx_str}_A"
        g_id2 = f"GW_{idx_str}_B"
        i_id = f"INV_{idx_str}"
        ord_id = f"ORD_{random.randint(100000, 999999)}"
        utr_num1 = f"UTR{random.randint(1000000000, 9999999999)}"
        utr_num2 = f"UTR{random.randint(1000000000, 9999999999)}"

        company_tuple = random.choice(COMPANY_NAMES)
        canonical_name = company_tuple[0]
        ref_num = f"{random.randint(100000, 999999)}"
        gross_amount = rand_amount()
        fee, tax, net_settlement = compute_fee_decomp(gross_amount)

        day_offset = random.randint(0, 20)
        inv_date = base_date + timedelta(days=day_offset)
        gw_date = inv_date + timedelta(days=1)
        bank_date = gw_date + timedelta(days=1)

        invoice_records.append({
            "invoice_id": i_id,
            "order_id": ord_id,
            "invoice_date": inv_date.strftime("%Y-%m-%d"),
            "due_date": (inv_date + timedelta(days=30)).strftime("%Y-%m-%d"),
            "customer_name": canonical_name,
            "customer_id": f"CUST_{random.randint(1000, 9999)}",
            "customer_email": f"billing@{canonical_name.lower().replace(' ', '')}.com",
            "amount": gross_amount,
            "tax_amount": round(gross_amount * 0.18, 2),
            "currency": "INR",
            "invoice_reference": f"INV-{ref_num}",
            "status": "PAID"
        })

        # Primary Gateway capture
        gateway_records.append({
            "gateway_txn_id": g_id1,
            "gateway_order_id": ord_id,
            "order_id": ord_id,
            "transaction_date": gw_date.strftime("%Y-%m-%d"),
            "amount": gross_amount,
            "gross_amount": gross_amount,
            "gateway_fee": fee,
            "tax_on_fee": tax,
            "net_settlement": net_settlement,
            "customer_name": canonical_name,
            "payment_reference": f"PAY-{ref_num}-1",
            "payment_method": "CARD",
            "gateway_name": "razorpay",
            "currency": "INR",
            "status": "CAPTURED"
        })

        # Duplicate Gateway collision (accidental double capture)
        gateway_records.append({
            "gateway_txn_id": g_id2,
            "gateway_order_id": ord_id,
            "order_id": ord_id,
            "transaction_date": gw_date.strftime("%Y-%m-%d"),
            "amount": gross_amount,
            "gross_amount": gross_amount,
            "gateway_fee": fee,
            "tax_on_fee": tax,
            "net_settlement": net_settlement,
            "customer_name": canonical_name,
            "payment_reference": f"PAY-{ref_num}-2",
            "payment_method": "CARD",
            "gateway_name": "razorpay",
            "currency": "INR",
            "status": "CAPTURED"
        })

        # Primary Bank credit
        bank_records.append({
            "bank_txn_id": b_id1,
            "transaction_date": bank_date.strftime("%Y-%m-%d"),
            "value_date": bank_date.strftime("%Y-%m-%d"),
            "amount": net_settlement,
            "credit_amount": net_settlement,
            "debit_amount": 0.0,
            "description": f"NEFT CR - {canonical_name.upper()} - REF {ref_num} DUP1 UTR {utr_num1}",
            "reference": f"REF-{ref_num}-1",
            "utr": utr_num1,
            "transaction_type": "CREDIT",
            "currency": "INR",
            "balance": round(random.uniform(500000.0, 5000000.0), 2)
        })

        # Duplicate Bank credit
        bank_records.append({
            "bank_txn_id": b_id2,
            "transaction_date": bank_date.strftime("%Y-%m-%d"),
            "value_date": bank_date.strftime("%Y-%m-%d"),
            "amount": net_settlement,
            "credit_amount": net_settlement,
            "debit_amount": 0.0,
            "description": f"NEFT CR - {canonical_name.upper()} - REF {ref_num} DUP2 UTR {utr_num2}",
            "reference": f"REF-{ref_num}-2",
            "utr": utr_num2,
            "transaction_type": "CREDIT",
            "currency": "INR",
            "balance": round(random.uniform(500000.0, 5000000.0), 2)
        })

        ground_truth_records.append({
            "bank_txn_id": b_id1,
            "gateway_txn_id": g_id1,
            "invoice_id": i_id,
            "order_id": ord_id,
            "expected_status": "MATCH",
            "expected_risk": "LOW",
            "amount": gross_amount,
            "discrepancy_reason": None,
            "exception_type": None
        })

        ground_truth_records.append({
            "bank_txn_id": b_id2,
            "gateway_txn_id": g_id2,
            "invoice_id": i_id,
            "order_id": ord_id,
            "expected_status": "DUPLICATE",
            "expected_risk": "HIGH",
            "amount": gross_amount,
            "discrepancy_reason": f"Duplicate payment capture detected for Order {ord_id}",
            "exception_type": "DUPLICATE_TRANSACTION"
        })

        current_idx += 1

    # =========================================================================
    # 6. Missing Records (~5%)
    # Missing Bank settlement, missing Gateway transaction, missing Invoice
    # =========================================================================
    for _ in range(n_missing):
        idx_str = fmt_id("TXN", current_idx)
        ord_id = f"ORD_{random.randint(100000, 999999)}"
        utr_num = f"UTR{random.randint(1000000000, 9999999999)}"
        company_tuple = random.choice(COMPANY_NAMES)
        canonical_name = company_tuple[0]
        ref_num = f"{random.randint(100000, 999999)}"
        gross_amount = rand_amount()
        fee, tax, net_settlement = compute_fee_decomp(gross_amount)
        day_offset = random.randint(0, 20)
        t_date = base_date + timedelta(days=day_offset)

        missing_type = random.choice(["missing_bank", "missing_gateway", "missing_invoice"])

        if missing_type == "missing_bank":
            g_id = f"GW_{idx_str}"
            i_id = f"INV_{idx_str}"

            invoice_records.append({
                "invoice_id": i_id,
                "order_id": ord_id,
                "invoice_date": t_date.strftime("%Y-%m-%d"),
                "due_date": (t_date + timedelta(days=30)).strftime("%Y-%m-%d"),
                "customer_name": canonical_name,
                "customer_id": f"CUST_{random.randint(1000, 9999)}",
                "customer_email": f"billing@{canonical_name.lower().replace(' ', '')}.com",
                "amount": gross_amount,
                "tax_amount": round(gross_amount * 0.18, 2),
                "currency": "INR",
                "invoice_reference": f"INV-{ref_num}",
                "status": "PAID"
            })
            gateway_records.append({
                "gateway_txn_id": g_id,
                "gateway_order_id": ord_id,
                "order_id": ord_id,
                "transaction_date": (t_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                "amount": gross_amount,
                "gross_amount": gross_amount,
                "gateway_fee": fee,
                "tax_on_fee": tax,
                "net_settlement": net_settlement,
                "customer_name": canonical_name,
                "payment_reference": f"PAY-{ref_num}",
                "payment_method": random.choice(PAYMENT_METHODS),
                "gateway_name": "razorpay",
                "currency": "INR",
                "status": "CAPTURED"
            })
            ground_truth_records.append({
                "bank_txn_id": None,
                "gateway_txn_id": g_id,
                "invoice_id": i_id,
                "order_id": ord_id,
                "expected_status": "MISSING",
                "expected_risk": "MEDIUM",
                "amount": gross_amount,
                "discrepancy_reason": "Gateway capture exists but payout is missing from Bank statement",
                "exception_type": "MISSING_BANK_SETTLEMENT"
            })

        elif missing_type == "missing_gateway":
            b_id = f"BNK_{idx_str}"
            i_id = f"INV_{idx_str}"

            invoice_records.append({
                "invoice_id": i_id,
                "order_id": ord_id,
                "invoice_date": t_date.strftime("%Y-%m-%d"),
                "due_date": (t_date + timedelta(days=30)).strftime("%Y-%m-%d"),
                "customer_name": canonical_name,
                "customer_id": f"CUST_{random.randint(1000, 9999)}",
                "customer_email": f"billing@{canonical_name.lower().replace(' ', '')}.com",
                "amount": gross_amount,
                "tax_amount": round(gross_amount * 0.18, 2),
                "currency": "INR",
                "invoice_reference": f"INV-{ref_num}",
                "status": "PAID"
            })
            bank_records.append({
                "bank_txn_id": b_id,
                "transaction_date": (t_date + timedelta(days=2)).strftime("%Y-%m-%d"),
                "value_date": (t_date + timedelta(days=2)).strftime("%Y-%m-%d"),
                "amount": gross_amount,
                "credit_amount": gross_amount,
                "debit_amount": 0.0,
                "description": f"DIRECT WIRE - {canonical_name.upper()} - {ref_num} UTR {utr_num}",
                "reference": f"REF-{ref_num}",
                "utr": utr_num,
                "transaction_type": "CREDIT",
                "currency": "INR",
                "balance": round(random.uniform(500000.0, 5000000.0), 2)
            })
            ground_truth_records.append({
                "bank_txn_id": b_id,
                "gateway_txn_id": None,
                "invoice_id": i_id,
                "order_id": ord_id,
                "expected_status": "MISSING",
                "expected_risk": "LOW",
                "amount": gross_amount,
                "discrepancy_reason": "Direct wire transfer recorded in bank without gateway mediation",
                "exception_type": "MISSING_GATEWAY_TRANSACTION"
            })

        else:  # missing_invoice
            b_id = f"BNK_{idx_str}"
            g_id = f"GW_{idx_str}"

            gateway_records.append({
                "gateway_txn_id": g_id,
                "gateway_order_id": ord_id,
                "order_id": ord_id,
                "transaction_date": t_date.strftime("%Y-%m-%d"),
                "amount": gross_amount,
                "gross_amount": gross_amount,
                "gateway_fee": fee,
                "tax_on_fee": tax,
                "net_settlement": net_settlement,
                "customer_name": canonical_name,
                "payment_reference": f"PAY-{ref_num}",
                "payment_method": random.choice(PAYMENT_METHODS),
                "gateway_name": "razorpay",
                "currency": "INR",
                "status": "CAPTURED"
            })
            bank_records.append({
                "bank_txn_id": b_id,
                "transaction_date": (t_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                "value_date": (t_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                "amount": net_settlement,
                "credit_amount": net_settlement,
                "debit_amount": 0.0,
                "description": f"NEFT CR - {canonical_name.upper()} - REF {ref_num} UTR {utr_num}",
                "reference": f"REF-{ref_num}",
                "utr": utr_num,
                "transaction_type": "CREDIT",
                "currency": "INR",
                "balance": round(random.uniform(500000.0, 5000000.0), 2)
            })
            ground_truth_records.append({
                "bank_txn_id": b_id,
                "gateway_txn_id": g_id,
                "invoice_id": None,
                "order_id": ord_id,
                "expected_status": "MISSING",
                "expected_risk": "MEDIUM",
                "amount": gross_amount,
                "discrepancy_reason": "Payment captured and settled but corresponding invoice missing in ERP",
                "exception_type": "MISSING_ERP_TRANSACTION"
            })

        current_idx += 1

    # =========================================================================
    # 7. Edge Cases (~10%)
    # Failed payment, refund/reversal, severe date lag
    # =========================================================================
    for _ in range(n_edge_cases):
        idx_str = fmt_id("TXN", current_idx)
        ord_id = f"ORD_{random.randint(100000, 999999)}"
        utr_num = f"UTR{random.randint(1000000000, 9999999999)}"
        company_tuple = random.choice(COMPANY_NAMES)
        canonical_name = company_tuple[0]
        ref_num = f"{random.randint(100000, 999999)}"
        gross_amount = rand_amount()
        fee, tax, net_settlement = compute_fee_decomp(gross_amount)
        day_offset = random.randint(0, 20)
        t_date = base_date + timedelta(days=day_offset)

        edge_type = random.choice(["failed_payment", "refund", "date_lag"])

        if edge_type == "failed_payment":
            g_id = f"GW_{idx_str}"
            i_id = f"INV_{idx_str}"

            invoice_records.append({
                "invoice_id": i_id,
                "order_id": ord_id,
                "invoice_date": t_date.strftime("%Y-%m-%d"),
                "due_date": (t_date + timedelta(days=30)).strftime("%Y-%m-%d"),
                "customer_name": canonical_name,
                "customer_id": f"CUST_{random.randint(1000, 9999)}",
                "customer_email": f"billing@{canonical_name.lower().replace(' ', '')}.com",
                "amount": gross_amount,
                "tax_amount": round(gross_amount * 0.18, 2),
                "currency": "INR",
                "invoice_reference": f"INV-{ref_num}",
                "status": "ISSUED"
            })
            gateway_records.append({
                "gateway_txn_id": g_id,
                "gateway_order_id": ord_id,
                "order_id": ord_id,
                "transaction_date": (t_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                "amount": gross_amount,
                "gross_amount": gross_amount,
                "gateway_fee": 0.0,
                "tax_on_fee": 0.0,
                "net_settlement": 0.0,
                "customer_name": canonical_name,
                "payment_reference": f"PAY-{ref_num}",
                "payment_method": "UPI",
                "gateway_name": "razorpay",
                "currency": "INR",
                "status": "FAILED"
            })
            ground_truth_records.append({
                "bank_txn_id": None,
                "gateway_txn_id": g_id,
                "invoice_id": i_id,
                "order_id": ord_id,
                "expected_status": "EXCEPTION",
                "expected_risk": "HIGH",
                "amount": gross_amount,
                "discrepancy_reason": "Payment gateway marked transaction as FAILED",
                "exception_type": "PAYMENT_FAILED"
            })

        elif edge_type == "refund":
            b_id = f"BNK_{idx_str}"
            g_id = f"GW_{idx_str}"
            i_id = f"INV_{idx_str}"

            invoice_records.append({
                "invoice_id": i_id,
                "order_id": ord_id,
                "invoice_date": t_date.strftime("%Y-%m-%d"),
                "due_date": (t_date + timedelta(days=30)).strftime("%Y-%m-%d"),
                "customer_name": canonical_name,
                "customer_id": f"CUST_{random.randint(1000, 9999)}",
                "customer_email": f"billing@{canonical_name.lower().replace(' ', '')}.com",
                "amount": gross_amount,
                "tax_amount": round(gross_amount * 0.18, 2),
                "currency": "INR",
                "invoice_reference": f"INV-{ref_num}",
                "status": "CANCELLED"
            })
            gateway_records.append({
                "gateway_txn_id": g_id,
                "gateway_order_id": ord_id,
                "order_id": ord_id,
                "transaction_date": (t_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                "amount": gross_amount,
                "gross_amount": gross_amount,
                "gateway_fee": 0.0,
                "tax_on_fee": 0.0,
                "net_settlement": -gross_amount,
                "customer_name": canonical_name,
                "payment_reference": f"PAY-{ref_num}",
                "payment_method": "CARD",
                "gateway_name": "razorpay",
                "currency": "INR",
                "status": "REFUNDED"
            })
            bank_records.append({
                "bank_txn_id": b_id,
                "transaction_date": (t_date + timedelta(days=3)).strftime("%Y-%m-%d"),
                "value_date": (t_date + timedelta(days=3)).strftime("%Y-%m-%d"),
                "amount": gross_amount,
                "credit_amount": 0.0,
                "debit_amount": gross_amount,
                "description": f"REVERSAL/REFUND - {canonical_name.upper()} - {ref_num} UTR {utr_num}",
                "reference": f"REF-{ref_num}",
                "utr": utr_num,
                "transaction_type": "DEBIT",
                "currency": "INR",
                "balance": round(random.uniform(500000.0, 5000000.0), 2)
            })
            ground_truth_records.append({
                "bank_txn_id": b_id,
                "gateway_txn_id": g_id,
                "invoice_id": i_id,
                "order_id": ord_id,
                "expected_status": "EXCEPTION",
                "expected_risk": "MEDIUM",
                "amount": gross_amount,
                "discrepancy_reason": "Order cancelled and payment refunded to customer",
                "exception_type": "REFUND"
            })

        else:  # date_lag (>10 days)
            b_id = f"BNK_{idx_str}"
            g_id = f"GW_{idx_str}"
            i_id = f"INV_{idx_str}"
            inv_d = t_date
            gw_d = inv_d + timedelta(days=12)
            bank_d = gw_d + timedelta(days=1)

            invoice_records.append({
                "invoice_id": i_id,
                "order_id": ord_id,
                "invoice_date": inv_d.strftime("%Y-%m-%d"),
                "due_date": (inv_d + timedelta(days=30)).strftime("%Y-%m-%d"),
                "customer_name": canonical_name,
                "customer_id": f"CUST_{random.randint(1000, 9999)}",
                "customer_email": f"billing@{canonical_name.lower().replace(' ', '')}.com",
                "amount": gross_amount,
                "tax_amount": round(gross_amount * 0.18, 2),
                "currency": "INR",
                "invoice_reference": f"INV-{ref_num}",
                "status": "PAID"
            })
            gateway_records.append({
                "gateway_txn_id": g_id,
                "gateway_order_id": ord_id,
                "order_id": ord_id,
                "transaction_date": gw_d.strftime("%Y-%m-%d"),
                "amount": gross_amount,
                "gross_amount": gross_amount,
                "gateway_fee": fee,
                "tax_on_fee": tax,
                "net_settlement": net_settlement,
                "customer_name": canonical_name,
                "payment_reference": f"PAY-{ref_num}",
                "payment_method": "UPI",
                "gateway_name": "razorpay",
                "currency": "INR",
                "status": "CAPTURED"
            })
            bank_records.append({
                "bank_txn_id": b_id,
                "transaction_date": bank_d.strftime("%Y-%m-%d"),
                "value_date": bank_d.strftime("%Y-%m-%d"),
                "amount": net_settlement,
                "credit_amount": net_settlement,
                "debit_amount": 0.0,
                "description": f"NEFT CR - {canonical_name.upper()} - REF {ref_num} UTR {utr_num}",
                "reference": f"REF-{ref_num}",
                "utr": utr_num,
                "transaction_type": "CREDIT",
                "currency": "INR",
                "balance": round(random.uniform(500000.0, 5000000.0), 2)
            })
            ground_truth_records.append({
                "bank_txn_id": b_id,
                "gateway_txn_id": g_id,
                "invoice_id": i_id,
                "order_id": ord_id,
                "expected_status": "REVIEW",
                "expected_risk": "LOW",
                "amount": gross_amount,
                "discrepancy_reason": "Extreme settlement lag (>10 days between invoice and payment)",
                "exception_type": "DATE_MISMATCH"
            })

        current_idx += 1

    # Shuffle to prevent order leaking ground truth
    random.shuffle(bank_records)
    random.shuffle(gateway_records)
    random.shuffle(invoice_records)

    # Convert to DataFrames and save CSVs
    df_bank = pd.DataFrame(bank_records)
    df_gw = pd.DataFrame(gateway_records)
    df_inv = pd.DataFrame(invoice_records)

    bank_csv_path = os.path.join(gen_dir, "bank_transactions.csv")
    gw_csv_path = os.path.join(gen_dir, "gateway_transactions.csv")
    inv_csv_path = os.path.join(gen_dir, "invoices.csv")
    gt_json_path = os.path.join(gt_dir, "ground_truth.json")

    df_bank.to_csv(bank_csv_path, index=False)
    df_gw.to_csv(gw_csv_path, index=False)
    df_inv.to_csv(inv_csv_path, index=False)

    with open(gt_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_records_requested": count,
                "bank_records_count": len(bank_records),
                "gateway_records_count": len(gateway_records),
                "invoice_records_count": len(invoice_records),
                "ground_truth_relationships": len(ground_truth_records),
                "distribution": {
                    "exact_matches": n_exact,
                    "many_to_one_batch_items": items_created,
                    "ambiguous_matches": n_ambiguous,
                    "fee_mismatches": n_fee_mismatch,
                    "duplicates": n_duplicates,
                    "missing": n_missing,
                    "edge_cases": n_edge_cases
                }
            },
            "records": ground_truth_records
        }, f, indent=2)

    print(f"=== Synthetic Financial Dataset Generated ===")
    print(f"Bank Transactions:     {len(bank_records):>4} rows -> {bank_csv_path}")
    print(f"Gateway Transactions:  {len(gateway_records):>4} rows -> {gw_csv_path}")
    print(f"Invoices:              {len(invoice_records):>4} rows -> {inv_csv_path}")
    print(f"Ground Truth Items:    {len(ground_truth_records):>4} items -> {gt_json_path}")
    print("=============================================")

    return {
        "bank_path": bank_csv_path,
        "gateway_path": gw_csv_path,
        "invoice_path": inv_csv_path,
        "ground_truth_path": gt_json_path,
        "bank_count": len(bank_records),
        "gateway_count": len(gateway_records),
        "invoice_count": len(invoice_records),
        "ground_truth_count": len(ground_truth_records),
    }


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic financial reconciliation datasets.")
    parser.add_argument("--count", type=int, default=250, help="Base count of transactions (e.g. 50, 100, 250, 500, 1000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output-dir", type=str, default="./data", help="Output directory for generated datasets")

    args = parser.parse_args()
    generate_synthetic_data(count=args.count, seed=args.seed, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
