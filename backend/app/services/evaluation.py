"""
Ground Truth Evaluation Service.

Problem Solved:
Calculates rigorous, unbiased empirical performance metrics (Precision, Recall,
F1 Score, False Positive Rate, Exception Detection Accuracy) by comparing
reconciliation decisions against an isolated ground truth benchmark.

Why It Exists:
To verify that the reconciliation pipeline adheres to the golden fintech rule:
'Never force an uncertain match' and to measure actual reconciliation quality.

Input:
Reconciliation results (from the database or pipeline run) and the isolated ground_truth.json benchmark.

Output:
Comprehensive evaluation report containing Precision, Recall, F1, FPR, FNR,
Confusion Matrix counts, and Exception Detection Accuracy.

Critical Rule:
Ground truth is strictly isolated and NEVER accessed during candidate generation,
scoring, or AI verification inference.
"""

import os
import json
from typing import Dict, Any, List, Optional


class EvaluationService:
    """
    Evaluates reconciliation pipeline decisions against isolated ground truth.
    """

    @staticmethod
    def load_ground_truth(ground_truth_path: str = "data/ground_truth/ground_truth.json") -> Optional[Dict[str, Any]]:
        """Safely loads ground truth benchmark if available on disk."""
        if not os.path.exists(ground_truth_path):
            return None
        try:
            with open(ground_truth_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    @classmethod
    def evaluate_run(
        cls,
        predicted_matches: List[Dict[str, Any]],
        ground_truth_path: str = "data/ground_truth/ground_truth.json",
    ) -> Dict[str, Any]:
        """
        Computes precision, recall, F1, confusion matrix, and error rates.
        """
        gt_data = cls.load_ground_truth(ground_truth_path)
        if not gt_data or "records" not in gt_data:
            return {
                "has_ground_truth": False,
                "message": "Ground truth benchmark not found. Run dataset generator to create ground_truth.json.",
            }

        gt_records = gt_data["records"]
        
        # Build lookup table of ground truth by tuple of (bank_id, gw_id, inv_id) or individual IDs
        gt_lookup = {}
        for r in gt_records:
            b = r.get("bank_txn_id")
            g = r.get("gateway_txn_id")
            i = r.get("invoice_id")
            key = (b, g, i)
            gt_lookup[key] = r
            if b:
                gt_lookup[f"b_{b}"] = r
            if g:
                gt_lookup[f"g_{g}"] = r
            if i:
                gt_lookup[f"i_{i}"] = r

        tp = 0 # Predicted MATCH, Actual MATCH
        fp = 0 # Predicted MATCH, Actual NOT MATCH (e.g. EXCEPTION / DUPLICATE)
        fn = 0 # Predicted NOT MATCH, Actual MATCH
        tn = 0 # Predicted NOT MATCH, Actual NOT MATCH

        correct_exceptions = 0
        total_gt_exceptions = 0

        for r in gt_records:
            if r.get("expected_status") in ("EXCEPTION", "DUPLICATE", "MISSING"):
                total_gt_exceptions += 1

        # Evaluate each prediction
        for pred in predicted_matches:
            b_id = pred.get("bank_txn_id")
            g_id = pred.get("gateway_txn_id")
            i_id = pred.get("invoice_id")
            decision = pred.get("decision", "REVIEW")

            # Find matching ground truth item
            gt_item = gt_lookup.get((b_id, g_id, i_id))
            if not gt_item:
                if b_id and f"b_{b_id}" in gt_lookup:
                    gt_item = gt_lookup[f"b_{b_id}"]
                elif g_id and f"g_{g_id}" in gt_lookup:
                    gt_item = gt_lookup[f"g_{g_id}"]
                elif i_id and f"i_{i_id}" in gt_lookup:
                    gt_item = gt_lookup[f"i_{i_id}"]

            if not gt_item:
                continue

            expected = gt_item.get("expected_status", "MATCH")

            if decision == "MATCH":
                if expected == "MATCH":
                    tp += 1
                else:
                    fp += 1
            else:
                # System flagged as REVIEW, EXCEPTION, DUPLICATE, or MISSING
                if expected == "MATCH":
                    fn += 1
                else:
                    tn += 1
                    if expected in ("EXCEPTION", "DUPLICATE", "MISSING") and decision in ("EXCEPTION", "REVIEW", "DUPLICATE", "MISSING"):
                        correct_exceptions += 1

        total_evaluated = tp + fp + fn + tn
        if total_evaluated == 0:
            return {
                "has_ground_truth": True,
                "total_records": 0,
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0,
            }

        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / total_evaluated if total_evaluated > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fnr = fn / (tp + fn) if (tp + fn) > 0 else 0.0
        exc_accuracy = min(1.0, correct_exceptions / total_gt_exceptions) if total_gt_exceptions > 0 else 1.0

        return {
            "has_ground_truth": True,
            "total_ground_truth_records": len(gt_records),
            "total_evaluated": total_evaluated,
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
            "false_positive_rate": round(fpr, 4),
            "false_negative_rate": round(fnr, 4),
            "exception_detection_accuracy": round(exc_accuracy, 4),
        }
