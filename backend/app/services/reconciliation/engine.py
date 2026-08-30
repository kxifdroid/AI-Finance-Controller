"""
Core Reconciliation Engine Orchestrator.

Problem Solved:
Coordinates the multi-layered financial reconciliation pipeline across Bank Statements,
Payment Gateway Logs, and ERP Invoices.

Why It Exists:
To execute chained 2-way reconciliations (Leg 1: Invoice ↔ Gateway, Leg 2: Gateway ↔ Bank),
perform many-to-one batch payout matching, scan for internal duplicates, enforce materiality control gates,
generate structured evidence chains, and classify unmatched transactions into canonical exception categories.

Architecture:
1. Duplicate Detection: Scans each source for internal collisions.
2. Leg 1 (Invoice ↔ Gateway): Layer 1 Exact -> Layer 2 Multi-Factor Fuzzy.
3. Leg 2 (Gateway ↔ Bank): Layer 1 Exact -> Layer 2 Fuzzy -> Many-to-One Settlement Matcher.
4. Chained 3-Way Assembly: Unifies legs into 3-way match audit records with evidence chains.
5. Exception Classification: Expanded taxonomy (MISSING_*, FEE_*, DUPLICATE_*, etc.).
6. Audit Logging & Run Metric Aggregation.
"""

import os
import json
import time
import uuid
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple, Set
from sqlalchemy.orm import Session

from app.config import settings
from app.models.transaction import BankTransaction, GatewayTransaction, Invoice
from app.models.reconciliation import ReconciliationRun, Match
from app.services.normalization import NormalizationService
from app.services.scoring import ScoringService
from app.services.exceptions import ExceptionService
from app.services.audit import AuditService
from app.services.reconciliation.evidence import EvidenceBuilder
from app.services.reconciliation.fee_calculator import FeeCalculator
from app.services.reconciliation.exact_matcher import ExactMatcher, can_auto_clear
from app.services.reconciliation.settlement_matcher import SettlementMatcher
from app.services.reconciliation.duplicate_detector import DuplicateDetector

logger = logging.getLogger(__name__)


class ReconciliationEngine:
    """
    Core orchestrator for multi-source financial reconciliation and exception triage.
    """

    def __init__(
        self,
        auto_match_threshold: float = settings.AUTO_MATCH_THRESHOLD,
        ai_review_threshold: float = settings.AI_REVIEW_THRESHOLD,
        amount_tolerance_pct: float = settings.AMOUNT_TOLERANCE_PCT,
        date_tolerance_days: int = settings.DATE_TOLERANCE_DAYS,
    ):
        self.auto_match_threshold = auto_match_threshold
        self.ai_review_threshold = ai_review_threshold
        self.amount_tolerance_pct = amount_tolerance_pct
        self.date_tolerance_days = date_tolerance_days
        self.scorer = ScoringService(date_max_tolerance_days=date_tolerance_days)

    def can_auto_clear(
        self,
        match_layer: str,
        confidence_score: float,
        amount: float,
        is_one_to_many: bool = False,
    ) -> bool:
        """
        Enforces the mandatory control gate for auto-clearing matches.
        Must pass confidence threshold AND monetary materiality ceiling (<= 5000.0)
        and must not be a many-to-one grouping.
        """
        return can_auto_clear(
            match_layer=match_layer,
            confidence_score=confidence_score,
            amount=amount,
            is_one_to_many=is_one_to_many,
        )

    def reconcile_two_way_leg(
        self,
        db: Session,
        run_id: str,
        side_a_records: List[Any],
        side_b_records: List[Any],
        leg_name: str,
        allow_fee_variance: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes a 2-way reconciliation pass between Side A and Side B.
        Layer 1 (Exact Matcher) runs first. Layer 2 (Fuzzy Matcher) runs on remaining unmatched items.

        Returns:
            Dict containing matched_pairs, review_pairs, matched_a_ids, matched_b_ids,
            remaining_a, and remaining_b.
        """
        # -------------------------------------------------------------
        # Layer 1: Exact Matcher
        # -------------------------------------------------------------
        exact_pairs, rem_a, rem_b, matched_a_ids, matched_b_ids = ExactMatcher.match(
            side_a_records=side_a_records,
            side_b_records=side_b_records,
            leg_name=leg_name,
            allow_fee_variance=allow_fee_variance,
        )

        matched_pairs: List[Dict[str, Any]] = []
        review_pairs: List[Dict[str, Any]] = []

        for p in exact_pairs:
            if p.get("decision") == "MATCH":
                matched_pairs.append(p)
            else:
                review_pairs.append(p)

        # -------------------------------------------------------------
        # Layer 2: Fuzzy Match on Remaining Unmatched Records
        # -------------------------------------------------------------
        for a in rem_a:
            a_id = getattr(a, "invoice_id", getattr(a, "gateway_txn_id", getattr(a, "bank_txn_id", None)))
            if a_id in matched_a_ids:
                continue

            a_ref = getattr(
                a,
                "normalized_ref",
                NormalizationService.normalize_reference(
                    getattr(a, "invoice_reference", getattr(a, "payment_reference", getattr(a, "reference", "")))
                ),
            )
            if allow_fee_variance:
                a_amt = float(
                    getattr(a, "net_settlement", None)
                    or getattr(a, "net_amount", None)
                    or getattr(a, "normalized_amount", getattr(a, "amount", 0.0))
                )
            else:
                a_amt = float(
                    getattr(a, "gross_amount", None)
                    or getattr(a, "normalized_amount", getattr(a, "amount", 0.0))
                )
            a_date = getattr(
                a,
                "normalized_date",
                getattr(a, "invoice_date", getattr(a, "transaction_date", date.today())),
            )
            a_cust = getattr(a, "customer_name", getattr(a, "description", ""))

            best_b = None
            best_score = 0.0
            best_features: Dict[str, float] = {}

            for b in rem_b:
                b_id = getattr(b, "gateway_txn_id", getattr(b, "bank_txn_id", getattr(b, "invoice_id", None)))
                if b_id in matched_b_ids:
                    continue

                b_amt = float(getattr(b, "normalized_amount", getattr(b, "amount", 0.0)))
                b_net = float(getattr(b, "net_settlement", 0.0) or getattr(b, "net_amount", 0.0) or 0.0)
                b_date = getattr(
                    b,
                    "normalized_date",
                    getattr(b, "transaction_date", getattr(b, "invoice_date", date.today())),
                )
                b_ref = getattr(
                    b,
                    "normalized_ref",
                    NormalizationService.normalize_reference(
                        getattr(b, "payment_reference", getattr(b, "reference", ""))
                    ),
                )
                b_cust = getattr(b, "customer_name", getattr(b, "description", ""))

                # Calculate multi-factor similarities
                amt_sim_gross = self.scorer.calculate_amount_similarity(a_amt, b_amt)
                amt_sim_net = (
                    self.scorer.calculate_amount_similarity(a_amt, b_net)
                    if (allow_fee_variance and b_net > 0)
                    else 0.0
                )
                amt_sim = max(amt_sim_gross, amt_sim_net)

                date_sim = self.scorer.calculate_date_similarity(a_date, b_date)
                ref_sim = self.scorer.calculate_reference_similarity(a_ref, b_ref)
                cust_sim = self.scorer.calculate_customer_similarity(a_cust, b_cust)

                score_res = self.scorer.compute_match_score(amt_sim, date_sim, ref_sim, cust_sim)
                if score_res["score"] > best_score:
                    best_score = score_res["score"]
                    best_b = b
                    best_features = score_res["features"]

            if best_b and best_score >= self.auto_match_threshold:
                b_id = getattr(best_b, "gateway_txn_id", getattr(best_b, "bank_txn_id", None))
                matched_a_ids.add(a_id)
                matched_b_ids.add(b_id)

                max_amt = max(abs(a_amt), abs(float(getattr(best_b, "amount", 0.0))))
                auto_cleared = self.can_auto_clear("layer2_fuzzy", best_score, max_amt)
                decision = "MATCH" if auto_cleared else "REVIEW"
                rule = "fuzzy_composite_score" if auto_cleared else "materiality_exceeded"

                evidence_json = EvidenceBuilder.build_match_evidence(
                    match_type="FUZZY",
                    rule=rule,
                    confidence=best_score,
                    side_a_fields={
                        "id": a_id,
                        "reference": a_ref,
                        "amount": a_amt,
                        "date": str(a_date),
                    },
                    side_b_fields={
                        "id": b_id,
                        "reference": getattr(best_b, "normalized_ref", ""),
                        "amount": float(getattr(best_b, "amount", 0.0)),
                        "date": str(getattr(best_b, "transaction_date", getattr(best_b, "invoice_date", ""))),
                    },
                    amounts={
                        "side_a_amount": round(a_amt, 2),
                        "side_b_amount": round(float(getattr(best_b, "amount", 0.0)), 2),
                        "amount_similarity": round(best_features.get("amount_similarity", 0.0), 4),
                    },
                    dates={
                        "side_a_date": str(a_date),
                        "side_b_date": str(getattr(best_b, "transaction_date", getattr(best_b, "invoice_date", ""))),
                        "date_similarity": round(best_features.get("date_similarity", 0.0), 4),
                    },
                    compared_fields={
                        "feature_decomposition": best_features,
                    },
                    policy_citation="Internal Control Policy 4.2 - Layer 2 Multi-Factor Fuzzy Matching",
                )
                amt_delta = abs(a_amt - float(getattr(best_b, "amount", 0.0)))
                soothing_fuzzy_exp = (
                    f"Candidate match ({int(best_score * 100)}% confidence). Reference '{a_ref}' matches with ₹{amt_delta:,.2f} variance on amount."
                    if amt_delta > 0.01
                    else f"Candidate match ({int(best_score * 100)}% confidence) based on multi-factor similarity scoring."
                )

                match_info = {
                    "side_a": a,
                    "side_b": best_b,
                    "match_layer": "layer2_fuzzy",
                    "match_rule": rule,
                    "match_type": "FUZZY",
                    "confidence": best_score,
                    "decision": decision,
                    "amount": max_amt,
                    "explanation": soothing_fuzzy_exp,
                    "evidence_json": evidence_json,
                    "features": best_features,
                }
                if auto_cleared:
                    matched_pairs.append(match_info)
                else:
                    review_pairs.append(match_info)

            elif best_b and best_score >= self.ai_review_threshold:
                b_id = getattr(best_b, "gateway_txn_id", getattr(best_b, "bank_txn_id", None))
                matched_a_ids.add(a_id)
                matched_b_ids.add(b_id)
                max_amt = max(abs(a_amt), abs(float(getattr(best_b, "amount", 0.0))))
                amt_delta = abs(a_amt - float(getattr(best_b, "amount", 0.0)))

                evidence_json = EvidenceBuilder.build_match_evidence(
                    match_type="FUZZY",
                    rule="review_confidence_floor",
                    confidence=best_score,
                    side_a_fields={"id": a_id, "amount": a_amt, "date": str(a_date)},
                    side_b_fields={"id": b_id, "amount": float(getattr(best_b, "amount", 0.0)), "date": str(getattr(best_b, "transaction_date", ""))},
                    compared_fields={"feature_decomposition": best_features},
                    policy_citation="Internal Control Policy 4.3 - Ambiguous Band Review Required",
                )

                review_pairs.append({
                    "side_a": a,
                    "side_b": best_b,
                    "match_layer": "layer2_fuzzy",
                    "match_rule": "review_confidence_floor",
                    "match_type": "FUZZY",
                    "confidence": best_score,
                    "decision": "REVIEW",
                    "amount": max_amt,
                    "explanation": f"Underpayment / variance detected ({int(best_score * 100)}% match confidence). Variance delta: ₹{amt_delta:,.2f}.",
                    "evidence_json": evidence_json,
                    "features": best_features,
                })

        final_rem_a = [
            a for a in side_a_records
            if getattr(a, "invoice_id", getattr(a, "gateway_txn_id", getattr(a, "bank_txn_id", None))) not in matched_a_ids
        ]
        final_rem_b = [
            b for b in side_b_records
            if getattr(b, "gateway_txn_id", getattr(b, "bank_txn_id", getattr(b, "invoice_id", None))) not in matched_b_ids
        ]

        return {
            "matched_pairs": matched_pairs,
            "review_pairs": review_pairs,
            "matched_a_ids": matched_a_ids,
            "matched_b_ids": matched_b_ids,
            "remaining_a": final_rem_a,
            "remaining_b": final_rem_b,
        }

    async def run_reconciliation(
        self,
        db: Session,
        use_ai: bool = False,
        dataset_id: Optional[str] = None,
        ground_truth_path: str = "data/ground_truth/ground_truth.json",
    ) -> ReconciliationRun:
        """
        Runs the comprehensive multi-source reconciliation pipeline:
        1. Duplicate Detection
        2. Leg 1: Invoice ↔ Gateway (Gross Matching)
        3. Leg 2: Gateway ↔ Bank (Net Settlement & Many-to-One Batch Matching)
        4. Chained 3-Way Match Assembly & Audit Trail Logging
        5. Expanded Exception Taxonomy Classification
        """
        start_time = time.time()
        run_id = f"RUN_{uuid.uuid4().hex[:10].upper()}"

        run = ReconciliationRun(
            run_id=run_id,
            dataset_id=dataset_id,
            status="RUNNING",
            started_at=datetime.now(),
            ai_enabled=use_ai,
        )
        db.add(run)
        db.commit()

        # Query records
        bank_q = db.query(BankTransaction)
        gateway_q = db.query(GatewayTransaction)
        invoice_q = db.query(Invoice)

        if dataset_id:
            bank_q = bank_q.filter(BankTransaction.dataset_id == dataset_id)
            gateway_q = gateway_q.filter(GatewayTransaction.dataset_id == dataset_id)
            invoice_q = invoice_q.filter(Invoice.dataset_id == dataset_id)

        bank_records = bank_q.all()
        gateway_records = gateway_q.all()
        invoice_records = invoice_q.all()

        total_input_records = len(bank_records) + len(gateway_records) + len(invoice_records)

        # -------------------------------------------------------------
        # Step 1: Duplicate Detection across all sources
        # -------------------------------------------------------------
        bank_dup_groups = DuplicateDetector.detect_duplicates(bank_records, "BANK")
        gw_dup_groups = DuplicateDetector.detect_duplicates(gateway_records, "GATEWAY")
        inv_dup_groups = DuplicateDetector.detect_duplicates(invoice_records, "INVOICE")

        total_duplicates = (
            sum(len(g["duplicate_records"]) for g in bank_dup_groups)
            + sum(len(g["duplicate_records"]) for g in gw_dup_groups)
            + sum(len(g["duplicate_records"]) for g in inv_dup_groups)
        )

        # -------------------------------------------------------------
        # Step 2: Chained Execution: Leg 1 (Invoice ↔ Gateway)
        # -------------------------------------------------------------
        leg1_res = self.reconcile_two_way_leg(
            db=db,
            run_id=run_id,
            side_a_records=invoice_records,
            side_b_records=gateway_records,
            leg_name="Leg 1: Invoice ↔ Gateway",
            allow_fee_variance=False,
        )

        # -------------------------------------------------------------
        # Step 3: Chained Execution: Leg 2 (Gateway ↔ Bank)
        # -------------------------------------------------------------
        leg2_res = self.reconcile_two_way_leg(
            db=db,
            run_id=run_id,
            side_a_records=gateway_records,
            side_b_records=bank_records,
            leg_name="Leg 2: Gateway ↔ Bank",
            allow_fee_variance=True,
        )

        # -------------------------------------------------------------
        # Step 4: Many-to-One Settlement Matching (Batch Deposits)
        # -------------------------------------------------------------
        unmatched_bank_for_batch = [
            b for b in bank_records
            if getattr(b, "bank_txn_id") not in leg2_res["matched_b_ids"]
        ]
        unmatched_gw_for_batch = [
            g for g in gateway_records
            if getattr(g, "gateway_txn_id") not in leg2_res["matched_a_ids"]
        ]

        batch_matches, batch_bank_ids, batch_gw_ids = SettlementMatcher.match_settlements(
            unmatched_banks=unmatched_bank_for_batch,
            unmatched_gateways=unmatched_gw_for_batch,
        )

        # Register batch matches in Leg 2 matched sets
        leg2_res["matched_b_ids"].update(batch_bank_ids)
        leg2_res["matched_a_ids"].update(batch_gw_ids)

        # -------------------------------------------------------------
        # Step 5: Assemble Chained 3-Way Match Records
        # -------------------------------------------------------------
        matched_count = 0
        review_count = 0
        exception_count = 0
        matched_vol = 0.0
        review_vol = 0.0
        exception_vol = 0.0

        # Build lookup for Leg 2 1-to-1 matches by gateway_txn_id
        gw_to_bank_match: Dict[str, Any] = {}
        for m in leg2_res["matched_pairs"] + leg2_res["review_pairs"]:
            gw_id = getattr(m["side_a"], "gateway_txn_id", None)
            if gw_id:
                gw_to_bank_match[gw_id] = m

        # Build lookup for batch settlement matches by gateway_txn_id
        gw_to_batch_match: Dict[str, Any] = {}
        for bm in batch_matches:
            for g in bm["gateway_records"]:
                gw_id = getattr(g, "gateway_txn_id", None)
                if gw_id:
                    gw_to_batch_match[gw_id] = bm

        # Process Invoices matched in Leg 1 -> build 3-way chain
        for m1 in leg1_res["matched_pairs"] + leg1_res["review_pairs"]:
            inv = m1["side_a"]
            gw = m1["side_b"]
            gw_id = getattr(gw, "gateway_txn_id", None)

            m2 = gw_to_bank_match.get(gw_id)
            bm = gw_to_batch_match.get(gw_id)

            bank = None
            m2_explanation = ""
            m2_rule = ""
            m2_evidence = None

            if m2:
                bank = m2["side_b"]
                m2_explanation = m2["explanation"]
                m2_rule = m2.get("match_rule", "leg2_matched")
                m2_evidence = m2.get("evidence_json")
            elif bm:
                bank = bm["bank_record"]
                m2_explanation = bm["explanation"]
                m2_rule = bm.get("match_rule", "batch_settlement")
                m2_evidence = bm.get("evidence_json")

            decision = m1["decision"]
            if (m2 and m2["decision"] == "REVIEW") or bm:
                decision = "REVIEW"

            m1_conf = float(m1.get("confidence", 1.0))
            m2_conf = float(m2.get("confidence", 0.95)) if m2 else (0.95 if bm else 0.5)
            confidence = min(m1_conf, m2_conf)
            max_amt = max(abs(float(getattr(inv, "amount", 0.0))), abs(float(getattr(gw, "amount", 0.0))))

            match_id = f"M_{uuid.uuid4().hex[:10].upper()}"

            # ------------------------------------------------------------------
            # Fee-aware 3-way classification
            # When the gateway charged a fee, expected bank credit = gross - fee - tax.
            # This is a deterministic calculation — the LLM is never involved.
            # ------------------------------------------------------------------
            fee_classification = None
            fee_breakdown_json = None
            gw_fee = float(getattr(gw, "gateway_fee", 0.0) or 0.0)
            gw_tax = float(getattr(gw, "tax_on_fee", 0.0) or 0.0)
            gw_gross = float(getattr(gw, "amount", 0.0) or 0.0)
            inv_amt = float(getattr(inv, "amount", 0.0) or 0.0)
            bank_credit = float(getattr(bank, "amount", 0.0) if bank else 0.0)
            fee_pct = 0.0

            if bank and gw_fee > 0:
                from app.services.reconciliation.fee_calculator import FeeCalculator
                is_valid, fee_pct_val, variance, fee_cls = FeeCalculator.validate_fee_variance(
                    gross_amount=gw_gross,
                    actual_bank_credit=bank_credit,
                    fee_amount=gw_fee,
                    tax_amount=gw_tax,
                )
                fee_pct = fee_pct_val
                fee_classification = fee_cls
                expected_net = FeeCalculator.calculate_fee_settlement(gw_gross, gw_fee, gw_tax)
                fee_breakdown_json = json.dumps({
                    "gross_amount": round(gw_gross, 2),
                    "gateway_fee": round(gw_fee, 2),
                    "tax_on_fee": round(gw_tax, 2),
                    "expected_net_settlement": round(expected_net, 2),
                    "actual_bank_credit": round(bank_credit, 2),
                    "variance": round(variance, 2),
                    "fee_pct": round(fee_pct * 100, 4),
                    "classification": fee_cls,
                })

            # Check if Leg 1 had underpayment / fuzzy review
            is_leg1_review = (m1.get("decision") == "REVIEW") or (abs(inv_amt - gw_gross) >= 0.01)

            # Determine match_type, decision, and risk_level cleanly
            if bm:
                match_type = "MANY_TO_ONE"
                decision = "REVIEW"
                risk_level = "LOW"
            elif is_leg1_review:
                match_type = "FUZZY"
                decision = "REVIEW"
                risk_level = "MEDIUM"
            elif fee_classification == "FEE_RECONCILED":
                match_type = "FEE_RECONCILED"
                decision = "MATCH"
                risk_level = "LOW"
            elif m2 and m2.get("match_type") == "TIMING_DIFFERENCE":
                match_type = "TIMING_DIFFERENCE"
                decision = "MATCH"
                risk_level = "LOW"
            elif not m2 and not bm:
                match_type = "MISSING_BANK_SETTLEMENT"
                decision = "REVIEW"
                risk_level = "HIGH"
            elif m1.get("match_type") == "EXACT" and m2 and m2.get("match_type") == "EXACT":
                match_type = "EXACT"
                decision = "MATCH"
                risk_level = "LOW"
            else:
                match_type = m1.get("match_type", "FUZZY")
                decision = "MATCH" if (m1.get("decision") == "MATCH" and (not m2 or m2.get("decision") == "MATCH")) else "REVIEW"
                risk_level = "LOW" if decision == "MATCH" else "MEDIUM"

            # Plain English Soothing Auditor Explanation
            ref_code = getattr(gw, "payment_reference", getattr(inv, "invoice_reference", getattr(bank, "reference", "")))
            cust_name = getattr(inv, "customer_name", getattr(gw, "customer_name", "Customer"))
            inv_id_str = getattr(inv, "invoice_id", "")
            gw_id_str = getattr(gw, "gateway_txn_id", "")

            if bm:
                soothing_exp = (
                    f"Batch payout reconciled: Bank deposit of ₹{bank_credit:,.2f} ({getattr(bank, 'description', getattr(bank, 'reference', ''))}) "
                    f"successfully aggregates {len(bm['gateway_records'])} gateway captures (including {ref_code} for ₹{gw_gross:,.2f})."
                )
                action_text = "Batch deposit verified against aggregate gateway captures."
            elif is_leg1_review and fee_classification == "FEE_RECONCILED":
                underpay_delta = round(abs(inv_amt - gw_gross), 2)
                soothing_exp = (
                    f"Partial match with customer underpayment: Leg 1 does not match fully — Invoice {inv_id_str} billed ₹{inv_amt:,.2f}, "
                    f"but Gateway {gw_id_str} captured only ₹{gw_gross:,.2f} (underpayment delta: ₹{underpay_delta:,.2f}, match confidence: {int(confidence * 100)}%). "
                    f"Leg 2 matches cleanly — Gateway collected ₹{gw_gross:,.2f} gross, deducted standard Razorpay fee of ₹{gw_fee:,.2f} ({fee_pct * 100:.2f}%) "
                    f"+ GST of ₹{gw_tax:,.2f} (18%), and Bank credited ₹{bank_credit:,.2f} net settlement with zero unexplained variance."
                )
                action_text = f"Follow up with {cust_name} for remaining ₹{underpay_delta:,.2f} invoice balance or issue a credit adjustment note."
            elif is_leg1_review:
                underpay_delta = round(abs(inv_amt - gw_gross), 2)
                soothing_exp = (
                    f"Underpayment variance detected: Invoice {inv_id_str} billed ₹{inv_amt:,.2f}, but Gateway {gw_id_str} captured ₹{gw_gross:,.2f} "
                    f"(variance delta: ₹{underpay_delta:,.2f}, match confidence: {int(confidence * 100)}%). "
                    + (m2_explanation if m2 else "[Leg 2] Bank settlement pending.")
                )
                action_text = f"Operator review required: Request balance payment of ₹{underpay_delta:,.2f} from {cust_name}."
            elif fee_classification == "FEE_RECONCILED":
                soothing_exp = (
                    f"Reconciled with standard Razorpay MDR fee deduction ({fee_pct * 100:.2f}% fee + 18% GST). "
                    f"Invoiced ₹{inv_amt:,.2f} gross; Bank received ₹{bank_credit:,.2f} net settlement with zero unexplained variance."
                )
                action_text = "No action required. Fee and GST deductions conform to standard fee schedule."
            elif m2 and m2.get("match_type") == "TIMING_DIFFERENCE":
                gw_d = getattr(gw, "transaction_date", date.today())
                bk_d = getattr(bank, "transaction_date", date.today())
                d_days = abs((bk_d - gw_d).days)
                soothing_exp = (
                    f"Reconciled across all systems with a {d_days}-day banking clearing delay "
                    f"(captured {gw_d}, credited {bk_d}). Reference '{ref_code}' and amount (₹{gw_gross:,.2f}) match exactly."
                )
                action_text = f"Settlement verified within permissible T+{d_days} bank clearing window."
            elif m2 and m1.get("match_type") == "EXACT":
                soothing_exp = (
                    f"Fully reconciled across ERP Invoice, Payment Gateway, and Bank Statement. "
                    f"Reference '{ref_code}', exact amount (₹{gw_gross:,.2f}), and same-day settlement date match identically."
                )
                action_text = "No action required. Transaction verified and reconciled."
            elif not m2 and not bm:
                soothing_exp = (
                    f"Payment captured via Gateway for ₹{gw_gross:,.2f} on {getattr(gw, 'transaction_date', '')}, "
                    f"but corresponding bank deposit has not been received (exceeds standard T+2 settlement window)."
                )
                action_text = "Trace bank settlement UTR with payment aggregator."
            else:
                soothing_exp = f"{m1['explanation']} " + (m2_explanation if m2 else "[Leg 2] Bank settlement pending.")
                action_text = "Reconciliation complete." if decision == "MATCH" else "Operator review required."

            # Combined structured evidence
            combined_evidence = m1.get("evidence_json") or EvidenceBuilder.build_match_evidence(
                match_type=match_type,
                rule=m1.get("match_rule", "chained_reconciliation"),
                confidence=confidence,
                amounts={"invoice_amount": float(getattr(inv, "amount", 0.0)), "gateway_amount": float(getattr(gw, "amount", 0.0))},
            )

            # Extract real similarity feature metrics from Leg 1 and Leg 2
            m1_features = m1.get("features") or {
                "amount_similarity": 1.0 if m1.get("match_type") == "EXACT" else round(m1_conf, 4),
                "date_similarity": 1.0,
                "reference_similarity": 1.0,
                "customer_similarity": 1.0,
            }
            if m2:
                m2_features = m2.get("features") or {
                    "amount_similarity": 1.0 if m2.get("match_type") == "EXACT" else 1.0,
                    "date_similarity": 1.0,
                    "reference_similarity": 1.0,
                    "customer_similarity": 1.0,
                }
            else:
                # Missing Leg 2 (no bank settlement): penalize the 3-way score.
                # Amount cleared is ₹0 vs expected -> amount similarity 0.0;
                # settlement date is pending -> date similarity 0.50.
                m2_features = {
                    "amount_similarity": 0.0,
                    "date_similarity": 0.50,
                    "reference_similarity": 1.0,
                    "customer_similarity": 1.0,
                }

            match_amt_sim = round(min(float(m1_features.get("amount_similarity", 1.0)), float(m2_features.get("amount_similarity", 0.0))), 4)
            match_date_sim = round(min(float(m1_features.get("date_similarity", 1.0)), float(m2_features.get("date_similarity", 0.50))), 4)
            match_ref_sim = round(min(float(m1_features.get("reference_similarity", 1.0)), float(m2_features.get("reference_similarity", 1.0))), 4)
            match_cust_sim = round(min(float(m1_features.get("customer_similarity", 1.0)), float(m2_features.get("customer_similarity", 1.0))), 4)

            match_record = Match(
                match_id=match_id,
                run_id=run_id,
                bank_txn_id=getattr(bank, "bank_txn_id", None),
                gateway_txn_id=gw_id,
                invoice_id=getattr(inv, "invoice_id", None),
                decision=decision,
                confidence_score=round(confidence, 4),
                risk_level=risk_level,
                explanation=soothing_exp,
                recommended_action=action_text,
                match_type=match_type,
                evidence_json=combined_evidence,
                fee_classification=fee_classification,
                fee_breakdown_json=fee_breakdown_json,
                amount_similarity=match_amt_sim,
                date_similarity=match_date_sim,
                reference_similarity=match_ref_sim,
                customer_similarity=match_cust_sim,
                composite_score=round(confidence, 4),
                verified_by_ai=False,
                ai_verification_status="NOT_REQUIRED",
            )
            db.add(match_record)

            # Structured Audit Log
            AuditService.log(
                db=db,
                entity_type="match",
                entity_id=match_id,
                action="auto_matched" if decision == "MATCH" else "classified",
                rule_or_reason=m1.get("match_rule", "chained_reconciliation"),
                actor="system",
                before_status=None,
                after_status=decision.lower(),
            )

            if decision == "MATCH":
                matched_count += 1
                matched_vol += max_amt
            else:
                review_count += 1
                review_vol += max_amt

        # Process Batch Settlement matches not already linked to an Invoice
        for bm in batch_matches:
            bank = bm["bank_record"]
            bank_id = getattr(bank, "bank_txn_id", None)
            for gw in bm["gateway_records"]:
                gw_id = getattr(gw, "gateway_txn_id", None)
                if gw_id and gw_id not in leg1_res["matched_b_ids"]:
                    match_id = f"M_{uuid.uuid4().hex[:10].upper()}"
                    gw_amt = float(getattr(gw, "amount", 0.0))
                    match_record = Match(
                        match_id=match_id,
                        run_id=run_id,
                        bank_txn_id=bank_id,
                        gateway_txn_id=gw_id,
                        invoice_id=None,
                        decision="REVIEW",
                        confidence_score=0.95,
                        risk_level="LOW",
                        explanation=bm["explanation"],
                        recommended_action="Approve batch settlement payout aggregation.",
                        match_type="MANY_TO_ONE",
                        evidence_json=bm.get("evidence_json"),
                        amount_similarity=1.0,
                        date_similarity=1.0,
                        reference_similarity=1.0,
                        customer_similarity=1.0,
                        composite_score=0.95,
                        verified_by_ai=False,
                        ai_verification_status="NOT_REQUIRED",
                    )
                    db.add(match_record)
                    AuditService.log(
                        db=db,
                        entity_type="match",
                        entity_id=match_id,
                        action="classified",
                        rule_or_reason="batch_settlement_sum_equality",
                        actor="system",
                        after_status="review",
                    )
                    review_count += 1
                    review_vol += gw_amt

        # -------------------------------------------------------------
        # Step 6: Classify Unmatched Records into Expanded Taxonomy
        # -------------------------------------------------------------
        # 1. Unmatched Invoices -> MISSING_GATEWAY_TRANSACTION
        unmatched_invoices = [
            i for i in invoice_records
            if getattr(i, "invoice_id") not in leg1_res["matched_a_ids"]
        ]
        for inv in unmatched_invoices:
            inv_amt = float(getattr(inv, "amount", 0.0))
            exc = ExceptionService.classify_and_create_exception(
                db=db,
                run_id=run_id,
                bank_record=None,
                gateway_record=None,
                invoice_record=inv,
                decision="EXCEPTION",
                reason=f"No matching payment gateway collection found for Invoice {getattr(inv, 'invoice_id')}.",
                recommended_action="Locate gateway collection or follow up on customer invoice payment.",
                suggested_type="MISSING_GATEWAY_TRANSACTION",
            )
            exception_count += 1
            exception_vol += inv_amt
            AuditService.log(
                db=db,
                entity_type="exception",
                entity_id=exc.exception_id,
                action="classified",
                rule_or_reason="missing_gateway_counterpart",
                actor="system",
                after_status="open",
            )

        # 2. Gateway records unmatched to Bank -> MISSING_BANK_SETTLEMENT / MISSING_ERP_TRANSACTION
        gw_to_inv_map = {
            getattr(m["side_b"], "gateway_txn_id"): m["side_a"]
            for m in leg1_res["matched_pairs"] + leg1_res["review_pairs"]
            if getattr(m.get("side_b"), "gateway_txn_id", None)
        }

        unmatched_gateways = [
            g for g in gateway_records
            if getattr(g, "gateway_txn_id") not in leg2_res["matched_a_ids"]
        ]
        for gw in unmatched_gateways:
            gw_id = getattr(gw, "gateway_txn_id")
            gw_amt = float(getattr(gw, "amount", 0.0))
            matched_inv = gw_to_inv_map.get(gw_id)
            is_invoiced = matched_inv is not None
            exc_type = "MISSING_BANK_SETTLEMENT" if is_invoiced else "MISSING_ERP_TRANSACTION"
            reason = (
                f"Gateway Transaction {gw_id} captured (Invoice {getattr(matched_inv, 'invoice_id', '')} linked) but bank settlement deposit not found."
                if is_invoiced
                else f"Gateway Transaction {gw_id} has no corresponding ERP invoice or bank settlement."
            )
            exc = ExceptionService.classify_and_create_exception(
                db=db,
                run_id=run_id,
                bank_record=None,
                gateway_record=gw,
                invoice_record=matched_inv,
                decision="EXCEPTION",
                reason=reason,
                recommended_action="Verify gateway payout schedule and settlement bank account." if is_invoiced else "Create ERP accrual invoice.",
                suggested_type=exc_type,
            )
            exception_count += 1
            exception_vol += gw_amt
            AuditService.log(
                db=db,
                entity_type="exception",
                entity_id=exc.exception_id,
                action="classified",
                rule_or_reason="missing_bank_settlement" if is_invoiced else "missing_erp_transaction",
                actor="system",
                after_status="open",
            )

        # 3. Orphan Bank Deposits -> MISSING_ERP_TRANSACTION
        unmatched_banks = [
            b for b in bank_records
            if getattr(b, "bank_txn_id") not in leg2_res["matched_b_ids"]
        ]
        for bank in unmatched_banks:
            bank_amt = float(getattr(bank, "amount", 0.0))
            exc = ExceptionService.classify_and_create_exception(
                db=db,
                run_id=run_id,
                bank_record=bank,
                gateway_record=None,
                invoice_record=None,
                decision="EXCEPTION",
                reason=f"Unallocated bank deposit of ₹{bank_amt:,.2f} on {getattr(bank, 'transaction_date', '')} ({getattr(bank, 'description', getattr(bank, 'reference', ''))}) with no corresponding ERP invoice or gateway payment record found.",
                recommended_action="Identify remittance entity and allocate to accounts receivable subledger.",
                suggested_type="MISSING_ERP_TRANSACTION",
            )
            exception_count += 1
            exception_vol += bank_amt
            AuditService.log(
                db=db,
                entity_type="exception",
                entity_id=exc.exception_id,
                action="classified",
                rule_or_reason="unallocated_bank_deposit",
                actor="system",
                after_status="open",
            )

        # 4. Record Duplicate Transaction Exceptions
        all_dup_groups = bank_dup_groups + gw_dup_groups + inv_dup_groups
        for grp in all_dup_groups:
            for dup_rec in grp["duplicate_records"]:
                dup_amt = float(getattr(dup_rec, "amount", 0.0))
                dup_id = getattr(dup_rec, "bank_txn_id", getattr(dup_rec, "gateway_txn_id", getattr(dup_rec, "invoice_id", None)))
                exc = ExceptionService.classify_and_create_exception(
                    db=db,
                    run_id=run_id,
                    bank_record=dup_rec if grp["source_type"] == "BANK" else None,
                    gateway_record=dup_rec if grp["source_type"] == "GATEWAY" else None,
                    invoice_record=dup_rec if grp["source_type"] == "INVOICE" else None,
                    decision="DUPLICATE",
                    reason=f"Duplicate record collision in {grp['source_type']}: {dup_id}",
                    recommended_action="Investigate duplicate entry and void duplicate charge/record.",
                    suggested_type="DUPLICATE_TRANSACTION",
                    suggested_severity="HIGH",
                    evidence_json=grp.get("evidence_json"),
                )
                AuditService.log(
                    db=db,
                    entity_type="exception",
                    entity_id=exc.exception_id,
                    action="classified",
                    rule_or_reason="duplicate_fingerprint_collision",
                    actor="system",
                    after_status="open",
                )

        end_time = time.time()
        elapsed_ms = (end_time - start_time) * 1000.0
        elapsed_sec = max(0.001, end_time - start_time)
        throughput = total_input_records / elapsed_sec

        run.status = "COMPLETED"
        run.completed_at = datetime.now()
        run.total_records = total_input_records
        run.matched_count = matched_count
        run.review_count = review_count
        run.exception_count = exception_count
        run.duplicate_count = total_duplicates
        run.missing_count = len(unmatched_invoices) + len(unmatched_gateways) + len(unmatched_banks)
        run.ai_escalation_count = 0
        run.processing_time_ms = round(elapsed_ms, 2)
        run.throughput_rps = round(throughput, 2)
        run.total_matched_volume = round(matched_vol, 2)
        run.total_exception_volume = round(exception_vol, 2)
        run.total_review_volume = round(review_vol, 2)

        db.commit()
        db.refresh(run)

        # Trigger ground truth evaluation if benchmark dataset exists
        if ground_truth_path and os.path.exists(ground_truth_path):
            try:
                from app.services.evaluation import EvaluationService
                from app.models.evaluation import EvaluationResult

                predicted_list = [
                    {
                        "bank_txn_id": m.bank_txn_id,
                        "gateway_txn_id": m.gateway_txn_id,
                        "invoice_id": m.invoice_id,
                        "decision": m.decision,
                    }
                    for m in run.matches
                ]
                eval_metrics = EvaluationService.evaluate_run(
                    predicted_matches=predicted_list,
                    ground_truth_path=ground_truth_path,
                )
                if eval_metrics.get("has_ground_truth"):
                    eval_rec = EvaluationResult(
                        run_id=run.run_id,
                        total_ground_truth_records=eval_metrics.get("total_ground_truth_records", 0),
                        accuracy=eval_metrics.get("accuracy", 0.0),
                        precision=eval_metrics.get("precision", 0.0),
                        recall=eval_metrics.get("recall", 0.0),
                        f1_score=eval_metrics.get("f1_score", 0.0),
                        false_positive_rate=eval_metrics.get("false_positive_rate", 0.0),
                        false_negative_rate=eval_metrics.get("false_negative_rate", 0.0),
                        exception_accuracy=eval_metrics.get("exception_detection_accuracy", 0.0),
                        true_positives=eval_metrics.get("true_positives", 0),
                        false_positives=eval_metrics.get("false_positives", 0),
                        false_negatives=eval_metrics.get("false_negatives", 0),
                        true_negatives=eval_metrics.get("true_negatives", 0),
                    )
                    db.add(eval_rec)
                    db.commit()
            except Exception as eval_err:
                logger.warning(f"Ground truth evaluation skipped: {eval_err}")

        logger.info(
            f"Reconciliation Engine run {run_id} completed in {elapsed_ms:.1f}ms: "
            f"{matched_count} matched, {review_count} review, {exception_count} exceptions, {total_duplicates} duplicates."
        )
        return run
