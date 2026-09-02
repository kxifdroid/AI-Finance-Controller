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
import re
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

    def reconcile(
        self,
        db: Session,
        use_ai: bool = False,
        dataset_id: Optional[str] = None,
        ground_truth_path: str = "data/ground_truth/ground_truth.json",
    ) -> ReconciliationRun:
        """Synchronous wrapper for run_reconciliation."""
        import asyncio
        return asyncio.run(self.run_reconciliation(
            db=db,
            use_ai=use_ai,
            dataset_id=dataset_id,
            ground_truth_path=ground_truth_path,
        ))

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
        # Step 5: Assemble Authoritative Chained Parent Reconciliation Records
        # -------------------------------------------------------------
        from app.services.reconciliation.canonical_codes import CanonicalReasonCode
        from app.services.reconciliation.explanation_builder import ExplanationBuilder

        matched_count = 0
        review_count = 0
        exception_count = 0
        matched_vol = 0.0
        review_vol = 0.0
        exception_vol = 0.0

        consumed_bank_ids: Set[str] = set()
        consumed_gw_ids: Set[str] = set()
        consumed_inv_ids: Set[str] = set()

        # Build lookup for Leg 2 1-to-1 matches by gateway_txn_id
        gw_to_bank_match: Dict[str, Any] = {}
        for m in leg2_res["matched_pairs"] + leg2_res["review_pairs"]:
            gw_id = getattr(m["side_a"], "gateway_txn_id", None)
            if gw_id:
                gw_to_bank_match[gw_id] = m

        # -------------------------------------------------------------
        # Pass 1: Assemble Batch Settlements (MANY_TO_ONE) as Single Parent Records
        # -------------------------------------------------------------
        for bm in batch_matches:
            bank = bm["bank_record"]
            gw_list = bm["gateway_records"]
            bank_id = getattr(bank, "bank_txn_id", None)
            gw_ids = [getattr(g, "gateway_txn_id") for g in gw_list if getattr(g, "gateway_txn_id")]

            if not bank_id or bank_id in consumed_bank_ids:
                continue

            # Identify all invoices linked to these gateway transactions in Leg 1
            inv_list = []
            for m1 in leg1_res["matched_pairs"] + leg1_res["review_pairs"]:
                m1_gw_id = getattr(m1["side_b"], "gateway_txn_id", None)
                if m1_gw_id in gw_ids:
                    inv_rec = m1["side_a"]
                    inv_id = getattr(inv_rec, "invoice_id", None)
                    if inv_id and inv_id not in consumed_inv_ids:
                        inv_list.append(inv_rec)
                        consumed_inv_ids.add(inv_id)

            # If no invoice linked via Leg 1, search remaining unmatched invoices matching reference or batch amount
            if not inv_list:
                for inv_rec in invoice_records:
                    inv_id = getattr(inv_rec, "invoice_id", None)
                    if inv_id not in consumed_inv_ids:
                        inv_ref = getattr(inv_rec, "invoice_reference", None)
                        bank_ref = getattr(bank, "reference", None)
                        inv_amt = float(getattr(inv_rec, "amount", 0.0))
                        bank_amt = float(getattr(bank, "amount", 0.0))
                        if (inv_ref and bank_ref and inv_ref == bank_ref) or abs(inv_amt - bank_amt) < 0.01:
                            inv_list.append(inv_rec)
                            consumed_inv_ids.add(inv_id)
                            break

            consumed_bank_ids.add(bank_id)
            consumed_gw_ids.update(gw_ids)

            bank_credit_total = float(getattr(bank, "amount", 0.0))
            gw_gross_total = round(sum(float(getattr(g, "amount", 0.0)) for g in gw_list), 2)
            gw_fee_total = round(sum(float(getattr(g, "gateway_fee", 0.0) or 0.0) for g in gw_list), 2)
            gw_tax_total = round(sum(float(getattr(g, "tax_on_fee", 0.0) or 0.0) for g in gw_list), 2)
            gw_net_total = round(sum(float(getattr(g, "net_settlement", None) or getattr(g, "net_amount", None) or getattr(g, "amount", 0.0)) for g in gw_list), 2)
            inv_total = round(sum(float(getattr(i, "amount", 0.0)) for i in inv_list), 2) if inv_list else bank_credit_total
            variance = round(bank_credit_total - gw_net_total, 2)

            if abs(variance) < 0.01:
                decision = "MATCH"
                match_type = "MANY_TO_ONE"
                reason_code = CanonicalReasonCode.MANY_TO_ONE_MATCH
                risk_level = "LOW"
                confidence = 1.0
            else:
                decision = "REVIEW"
                match_type = "MANY_TO_ONE"
                reason_code = CanonicalReasonCode.AMOUNT_MISMATCH
                risk_level = "MEDIUM"
                confidence = 0.85

            amounts_dict = {
                "invoice_total": inv_total,
                "gateway_gross_total": gw_gross_total,
                "gateway_fee_total": gw_fee_total,
                "gateway_tax_total": gw_tax_total,
                "gateway_net_total": gw_net_total,
                "bank_credit_total": bank_credit_total,
                "variance": variance,
            }

            exp_data = ExplanationBuilder.build_explanation_and_action(
                decision=decision,
                reason_code=reason_code,
                amounts=amounts_dict,
                context={
                    "gateway_count": len(gw_list),
                    "reference": getattr(bank, "reference", getattr(gw_list[0], "payment_reference", "")),
                    "bank_date": str(getattr(bank, "transaction_date", "")),
                },
            )

            match_id = f"M_{uuid.uuid4().hex[:10].upper()}"
            match_record = Match(
                match_id=match_id,
                run_id=run_id,
                topology="MANY_TO_ONE",
                reason_code=reason_code,
                bank_txn_id=bank_id,
                gateway_txn_id=gw_ids[0] if gw_ids else None,
                invoice_id=getattr(inv_list[0], "invoice_id", None) if inv_list else None,
                bank_txn_ids_json=json.dumps([bank_id]),
                gateway_txn_ids_json=json.dumps(gw_ids),
                invoice_ids_json=json.dumps([getattr(i, "invoice_id") for i in inv_list]),
                amounts_json=json.dumps(amounts_dict),
                primary_amount=bank_credit_total,
                expected_amount=gw_net_total,
                settled_amount=bank_credit_total,
                variance_amount=variance,
                decision=decision,
                confidence_score=round(confidence, 4),
                deterministic_confidence=round(confidence, 4),
                risk_level=risk_level,
                explanation=exp_data["explanation"],
                recommended_action=exp_data["recommended_action"],
                match_type=match_type,
                evidence_json=bm.get("evidence_json"),
                amount_similarity=1.0 if abs(variance) < 0.01 else 0.85,
                date_similarity=1.0,
                reference_similarity=1.0,
                customer_similarity=1.0,
                composite_score=round(confidence, 4),
                verified_by_ai=False,
                ai_verification_status="NOT_REQUIRED",
            )
            db.add(match_record)

            AuditService.log(
                db=db,
                entity_type="match",
                entity_id=match_id,
                action="auto_matched" if decision == "MATCH" else "classified",
                rule_or_reason=reason_code,
                actor="system",
                after_status=decision.lower(),
            )

            if decision == "MATCH":
                matched_count += 1
                matched_vol += bank_credit_total
            else:
                review_count += 1
                review_vol += bank_credit_total

        # -------------------------------------------------------------
        # Pass 2: Assemble 1-to-1 Matches from Leg 1 Pairs
        # -------------------------------------------------------------
        for m1 in leg1_res["matched_pairs"] + leg1_res["review_pairs"]:
            inv = m1["side_a"]
            gw = m1["side_b"]
            gw_id = getattr(gw, "gateway_txn_id", None)
            inv_id = getattr(inv, "invoice_id", None)

            if not gw_id or gw_id in consumed_gw_ids or (inv_id and inv_id in consumed_inv_ids):
                continue

            m2 = gw_to_bank_match.get(gw_id)
            bank = m2["side_b"] if m2 else None
            bank_id = getattr(bank, "bank_txn_id", None) if bank else None

            if bank_id and bank_id in consumed_bank_ids:
                bank = None
                bank_id = None
                m2 = None

            consumed_gw_ids.add(gw_id)
            if inv_id:
                consumed_inv_ids.add(inv_id)
            if bank_id:
                consumed_bank_ids.add(bank_id)

            inv_amt = float(getattr(inv, "amount", 0.0))
            gw_gross = float(getattr(gw, "amount", 0.0))
            gw_fee = float(getattr(gw, "gateway_fee", 0.0) or 0.0)
            gw_tax = float(getattr(gw, "tax_on_fee", 0.0) or 0.0)
            gw_net = gw_gross - gw_fee - gw_tax if gw_fee > 0 else gw_gross
            bank_credit = float(getattr(bank, "amount", 0.0) if bank else 0.0)
            variance = round(bank_credit - gw_net if bank else gw_gross, 2)

            # Compute features
            amt_sim = self.scorer.calculate_3way_amount_similarity(inv_amt, gw_gross, gw_fee, gw_tax, bank_credit if bank else None)
            gw_date = getattr(gw, 'transaction_date', None)
            bank_date = getattr(bank, 'transaction_date', None) if bank else None
            date_sim = self.scorer.calculate_date_similarity(gw_date, bank_date) if (gw_date and bank_date) else (0.50 if not bank else 1.0)
            ref_sim = self.scorer.calculate_reference_similarity(getattr(inv, 'invoice_reference', ''), getattr(gw, 'payment_reference', ''))
            cust_sim = self.scorer.calculate_customer_similarity(getattr(inv, 'customer_name', ''), getattr(gw, 'customer_name', ''))
            computed = self.scorer.compute_match_score(amt_sim, date_sim, ref_sim, cust_sim)
            confidence = computed["score"]

            fee_classification = None
            fee_breakdown_json = None
            if bank and gw_fee > 0:
                is_valid, fee_pct_val, fee_var, fee_cls = FeeCalculator.validate_fee_variance(
                    gross_amount=gw_gross,
                    actual_bank_credit=bank_credit,
                    fee_amount=gw_fee,
                    tax_amount=gw_tax,
                )
                fee_classification = fee_cls
                expected_net = FeeCalculator.calculate_fee_settlement(gw_gross, gw_fee, gw_tax)
                fee_breakdown_json = json.dumps({
                    "gross_amount": round(gw_gross, 2),
                    "gateway_fee": round(gw_fee, 2),
                    "tax_on_fee": round(gw_tax, 2),
                    "expected_net_settlement": round(expected_net, 2),
                    "actual_bank_credit": round(bank_credit, 2),
                    "variance": round(variance, 2),
                    "fee_pct": round(fee_pct_val * 100, 4),
                    "classification": fee_cls,
                })

            # Authoritative Final Classification Pass
            if not bank:
                decision = "REVIEW"
                match_type = "MISSING_BANK_SETTLEMENT"
                reason_code = CanonicalReasonCode.MISSING_BANK_SETTLEMENT
                risk_level = "HIGH"
                amt_sim = 0.0
                date_sim = 0.50
                computed = self.scorer.compute_match_score(amt_sim, date_sim, ref_sim, cust_sim)
                confidence = round(computed["score"], 4)
            elif gw_fee > 0:
                if fee_classification == "FEE_RECONCILED" and abs(inv_amt - gw_gross) < 0.01:
                    decision = "MATCH"
                    match_type = "FEE_RECONCILED"
                    reason_code = CanonicalReasonCode.FEE_RECONCILED
                    risk_level = "LOW"
                    confidence = 1.0
                    amt_sim = 1.0
                elif abs(inv_amt - gw_gross) >= 0.01:
                    decision = "REVIEW"
                    match_type = "AMOUNT_MISMATCH"
                    reason_code = CanonicalReasonCode.AMOUNT_MISMATCH
                    risk_level = "MEDIUM"
                    confidence = round(computed["score"], 4)
                else:
                    decision = "REVIEW"
                    match_type = "FEE_VARIANCE"
                    reason_code = CanonicalReasonCode.FEE_VARIANCE
                    risk_level = "HIGH"
                    amt_sim = 0.50
                    computed = self.scorer.compute_match_score(amt_sim, date_sim, ref_sim, cust_sim)
                    confidence = round(computed["score"], 4)
            else:
                diff_inv_gw = abs(inv_amt - gw_gross)
                diff_gw_bank = abs(gw_gross - bank_credit)
                if diff_inv_gw < 0.01 and diff_gw_bank < 0.01:
                    if m2 and m2.get("match_type") == "TIMING_DIFFERENCE":
                        decision = "MATCH"
                        match_type = "TIMING_DIFFERENCE"
                        reason_code = CanonicalReasonCode.TIMING_DIFFERENCE
                        risk_level = "LOW"
                        confidence = float(m2.get("confidence", 0.98))
                    else:
                        decision = "MATCH"
                        match_type = "EXACT"
                        reason_code = CanonicalReasonCode.EXACT_3_WAY_MATCH
                        risk_level = "LOW"
                        confidence = 1.0
                else:
                    # Amount Mismatch across 3-way records
                    decision = "REVIEW"
                    match_type = "AMOUNT_MISMATCH"
                    reason_code = CanonicalReasonCode.AMOUNT_MISMATCH
                    risk_level = "MEDIUM"
                    confidence = round(computed["score"], 4)

            amounts_dict = {
                "invoice_total": inv_amt,
                "gateway_gross_total": gw_gross,
                "gateway_fee_total": gw_fee,
                "gateway_tax_total": gw_tax,
                "gateway_net_total": gw_net,
                "bank_credit_total": bank_credit,
                "variance": variance,
            }

            gw_d_str = str(getattr(gw, "transaction_date", ""))
            bk_d_str = str(getattr(bank, "transaction_date", "")) if bank else ""
            delta_days = abs((getattr(bank, "transaction_date", date.today()) - getattr(gw, "transaction_date", date.today())).days) if bank else 0

            exp_data = ExplanationBuilder.build_explanation_and_action(
                decision=decision,
                reason_code=reason_code,
                amounts=amounts_dict,
                context={
                    "reference": getattr(gw, "payment_reference", getattr(inv, "invoice_reference", "")),
                    "customer": getattr(inv, "customer_name", getattr(gw, "customer_name", "Customer")),
                    "fee_cls": fee_classification,
                    "gateway_date": gw_d_str,
                    "bank_date": bk_d_str,
                    "delta_days": delta_days,
                },
            )

            match_id = f"M_{uuid.uuid4().hex[:10].upper()}"
            match_record = Match(
                match_id=match_id,
                run_id=run_id,
                topology="ONE_TO_ONE",
                reason_code=reason_code,
                bank_txn_id=bank_id,
                gateway_txn_id=gw_id,
                invoice_id=inv_id,
                bank_txn_ids_json=json.dumps([bank_id] if bank_id else []),
                gateway_txn_ids_json=json.dumps([gw_id] if gw_id else []),
                invoice_ids_json=json.dumps([inv_id] if inv_id else []),
                amounts_json=json.dumps(amounts_dict),
                primary_amount=inv_amt if inv_amt > 0 else gw_gross,
                expected_amount=gw_net if bank else gw_gross,
                settled_amount=bank_credit,
                variance_amount=variance,
                decision=decision,
                confidence_score=round(confidence, 4),
                deterministic_confidence=round(confidence, 4),
                risk_level=risk_level,
                explanation=exp_data["explanation"],
                recommended_action=exp_data["recommended_action"],
                match_type=match_type,
                evidence_json=m1.get("evidence_json"),
                fee_classification=fee_classification,
                fee_breakdown_json=fee_breakdown_json,
                amount_similarity=round(amt_sim, 4),
                date_similarity=round(date_sim, 4),
                reference_similarity=round(ref_sim, 4),
                customer_similarity=round(cust_sim, 4),
                composite_score=round(confidence, 4),
                verified_by_ai=False,
                ai_verification_status="NOT_REQUIRED",
            )
            db.add(match_record)

            AuditService.log(
                db=db,
                entity_type="match",
                entity_id=match_id,
                action="auto_matched" if decision == "MATCH" else "classified",
                rule_or_reason=reason_code,
                actor="system",
                after_status=decision.lower(),
            )

            max_amt = max(inv_amt, gw_gross)
            if decision == "MATCH":
                matched_count += 1
                matched_vol += max_amt
            else:
                review_count += 1
                review_vol += max_amt

        # -------------------------------------------------------------
        # Pass 3: Assemble Leg 2 Pairs where Gateway had no Invoice counterpart
        # -------------------------------------------------------------
        for m2 in leg2_res["matched_pairs"] + leg2_res["review_pairs"]:
            gw = m2["side_a"]
            bank = m2["side_b"]
            gw_id = getattr(gw, "gateway_txn_id", None)
            bank_id = getattr(bank, "bank_txn_id", None)

            if not gw_id or gw_id in consumed_gw_ids or not bank_id or bank_id in consumed_bank_ids:
                continue

            consumed_gw_ids.add(gw_id)
            consumed_bank_ids.add(bank_id)

            gw_gross = float(getattr(gw, "amount", 0.0))
            bank_credit = float(getattr(bank, "amount", 0.0))
            variance = round(bank_credit - gw_gross, 2)

            amounts_dict = {
                "invoice_total": 0.0,
                "gateway_gross_total": gw_gross,
                "gateway_fee_total": 0.0,
                "gateway_tax_total": 0.0,
                "gateway_net_total": gw_gross,
                "bank_credit_total": bank_credit,
                "variance": variance,
            }

            reason_code = CanonicalReasonCode.MISSING_INVOICE
            decision = "REVIEW"
            risk_level = "MEDIUM"

            # Compute features for Missing Invoice (missing ERP leg)
            amt_sim = 0.50 if abs(variance) < 0.01 else 0.25
            date_sim = 1.0
            ref_sim = 1.0
            cust_sim = 1.0
            computed = self.scorer.compute_match_score(amt_sim, date_sim, ref_sim, cust_sim)
            confidence = round(computed["score"], 4)

            exp_data = ExplanationBuilder.build_explanation_and_action(
                decision=decision,
                reason_code=reason_code,
                amounts=amounts_dict,
                context={
                    "reference": getattr(gw, "payment_reference", ""),
                    "customer": getattr(gw, "customer_name", "Customer"),
                },
            )

            match_id = f"M_{uuid.uuid4().hex[:10].upper()}"
            match_record = Match(
                match_id=match_id,
                run_id=run_id,
                topology="ONE_TO_ONE",
                reason_code=reason_code,
                bank_txn_id=bank_id,
                gateway_txn_id=gw_id,
                invoice_id=None,
                bank_txn_ids_json=json.dumps([bank_id]),
                gateway_txn_ids_json=json.dumps([gw_id]),
                invoice_ids_json=json.dumps([]),
                amounts_json=json.dumps(amounts_dict),
                primary_amount=gw_gross,
                expected_amount=gw_gross,
                settled_amount=bank_credit,
                variance_amount=variance,
                decision=decision,
                confidence_score=round(confidence, 4),
                deterministic_confidence=round(confidence, 4),
                risk_level=risk_level,
                explanation=exp_data["explanation"],
                recommended_action=exp_data["recommended_action"],
                match_type="MISSING_INVOICE",
                evidence_json=m2.get("evidence_json"),
                amount_similarity=round(amt_sim, 4),
                date_similarity=round(date_sim, 4),
                reference_similarity=round(ref_sim, 4),
                customer_similarity=round(cust_sim, 4),
                composite_score=round(confidence, 4),
                verified_by_ai=False,
                ai_verification_status="NOT_REQUIRED",
            )
            db.add(match_record)
            review_count += 1
            review_vol += gw_gross

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
