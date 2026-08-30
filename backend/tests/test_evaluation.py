"""
Unit tests for EvaluationService.
"""

from app.services.evaluation import EvaluationService


def test_evaluation_metrics_calculation(tmp_path):
    # Create temporary ground truth file
    import json
    gt_file = tmp_path / "ground_truth.json"
    
    gt_data = {
        "records": [
            {"bank_txn_id": "B1", "gateway_txn_id": "G1", "invoice_id": "I1", "expected_status": "MATCH"},
            {"bank_txn_id": "B2", "gateway_txn_id": "G2", "invoice_id": "I2", "expected_status": "MATCH"},
            {"bank_txn_id": "B3", "gateway_txn_id": "G3", "invoice_id": "I3", "expected_status": "EXCEPTION"},
            {"bank_txn_id": "B4", "gateway_txn_id": "G4", "invoice_id": "I4", "expected_status": "DUPLICATE"},
        ]
    }
    gt_file.write_text(json.dumps(gt_data), encoding="utf-8")

    # Predicted outcomes
    predictions = [
        {"bank_txn_id": "B1", "gateway_txn_id": "G1", "invoice_id": "I1", "decision": "MATCH"}, # TP
        {"bank_txn_id": "B2", "gateway_txn_id": "G2", "invoice_id": "I2", "decision": "MATCH"}, # TP
        {"bank_txn_id": "B3", "gateway_txn_id": "G3", "invoice_id": "I3", "decision": "EXCEPTION"}, # TN (correct exception)
        {"bank_txn_id": "B4", "gateway_txn_id": "G4", "invoice_id": "I4", "decision": "DUPLICATE"}, # TN (correct duplicate)
    ]

    results = EvaluationService.evaluate_run(predictions, ground_truth_path=str(gt_file))
    
    assert results["has_ground_truth"] is True
    assert results["precision"] == 1.0
    assert results["recall"] == 1.0
    assert results["f1_score"] == 1.0
    assert results["true_positives"] == 2
    assert results["true_negatives"] == 2
    assert results["false_positives"] == 0
    assert results["false_negatives"] == 0
    assert results["exception_detection_accuracy"] == 1.0
