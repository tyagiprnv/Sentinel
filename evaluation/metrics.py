"""
Metrics calculation for PII redaction evaluation.

Computes precision, recall, F1 score, and entity-level metrics.
"""
from typing import List, Dict, Tuple
import re


def extract_predicted_entities(original_text: str, redacted_text: str, scores: List[float]) -> List[Dict]:
    """
    Extract predicted entities by comparing original and redacted text.

    Args:
        original_text: Original text before redaction
        redacted_text: Text after redaction with [REDACTED_xxxx] tokens
        scores: Confidence scores from Presidio

    Returns:
        List of predicted entities with positions
    """
    predictions = []

    # Find all redaction tokens
    tokens = list(re.finditer(r'\[REDACTED_[a-z0-9]+\]', redacted_text))

    # Track position offset as we iterate
    offset = 0
    pred_idx = 0

    for match in tokens:
        token_start = match.start()
        token_end = match.end()
        token_text = match.group()

        # Find corresponding text in original
        # This is approximate since we don't know exact boundaries
        # We'll mark the position where the token appears
        predictions.append({
            "start": token_start,
            "end": token_end,
            "text": token_text,
            "score": scores[pred_idx] if pred_idx < len(scores) else 0.0,
            "type": "REDACTED"  # Type unknown without analyzer results
        })
        pred_idx += 1

    return predictions


def calculate_entity_overlap(pred: Dict, truth: Dict) -> float:
    """
    Calculate overlap between predicted and ground truth entity.

    Args:
        pred: Predicted entity with start/end positions
        truth: Ground truth entity with start/end positions

    Returns:
        Jaccard similarity score (intersection over union)
    """
    pred_start, pred_end = pred["start"], pred["end"]
    truth_start, truth_end = truth["start"], truth["end"]

    # Calculate intersection
    intersection_start = max(pred_start, truth_start)
    intersection_end = min(pred_end, truth_end)
    intersection = max(0, intersection_end - intersection_start)

    # Calculate union
    union_start = min(pred_start, truth_start)
    union_end = max(pred_end, truth_end)
    union = union_end - union_start

    return intersection / union if union > 0 else 0.0


def match_entities(predictions: List[Dict], ground_truth: List[Dict], threshold: float = 0.5) -> Tuple[List, List, List]:
    """
    Match predicted entities with ground truth using overlap threshold.

    Args:
        predictions: List of predicted entities
        ground_truth: List of ground truth entities
        threshold: Minimum overlap to consider a match

    Returns:
        Tuple of (true_positives, false_positives, false_negatives)
    """
    true_positives = []
    false_positives = []
    false_negatives = []

    matched_truth_indices = set()

    # For each prediction, find best matching ground truth
    for pred in predictions:
        best_match = None
        best_overlap = 0.0
        best_idx = -1

        for idx, truth in enumerate(ground_truth):
            if idx in matched_truth_indices:
                continue

            overlap = calculate_entity_overlap(pred, truth)
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = truth
                best_idx = idx

        if best_overlap >= threshold:
            true_positives.append({
                "prediction": pred,
                "ground_truth": best_match,
                "overlap": best_overlap
            })
            matched_truth_indices.add(best_idx)
        else:
            false_positives.append(pred)

    # Unmatched ground truth entities are false negatives
    for idx, truth in enumerate(ground_truth):
        if idx not in matched_truth_indices:
            false_negatives.append(truth)

    return true_positives, false_positives, false_negatives


def calculate_metrics(true_positives: int, false_positives: int, false_negatives: int) -> Dict:
    """
    Calculate precision, recall, and F1 score.

    Args:
        true_positives: Number of correct predictions
        false_positives: Number of incorrect predictions (over-redaction)
        false_negatives: Number of missed entities (under-redaction)

    Returns:
        Dictionary with precision, recall, F1, and counts
    """
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives
    }


def calculate_metrics_by_type(all_matches: List[Dict], all_fps: List[Dict], all_fns: List[Dict]) -> Dict:
    """
    Calculate metrics broken down by entity type.

    Args:
        all_matches: All true positive matches
        all_fps: All false positives
        all_fns: All false negatives

    Returns:
        Dictionary mapping entity type to metrics
    """
    type_metrics = {}

    # Count by ground truth type
    type_counts = {"tp": {}, "fp": {}, "fn": {}}

    # True positives
    for match in all_matches:
        entity_type = match["ground_truth"]["type"]
        type_counts["tp"][entity_type] = type_counts["tp"].get(entity_type, 0) + 1

    # False negatives (missed entities)
    for fn in all_fns:
        entity_type = fn["type"]
        type_counts["fn"][entity_type] = type_counts["fn"].get(entity_type, 0) + 1

    # Calculate metrics per type
    all_types = set(list(type_counts["tp"].keys()) + list(type_counts["fn"].keys()))

    for entity_type in all_types:
        tp = type_counts["tp"].get(entity_type, 0)
        fp = 0  # Hard to attribute FPs to specific type without predictions having types
        fn = type_counts["fn"].get(entity_type, 0)

        type_metrics[entity_type] = calculate_metrics(tp, fp, fn)

    return type_metrics


def calculate_latency_metrics(latencies: List[float]) -> Dict:
    """
    Calculate latency statistics.

    Args:
        latencies: List of latency measurements in seconds

    Returns:
        Dictionary with p50, p95, p99, mean, max
    """
    import numpy as np

    if not latencies:
        return {"p50": 0, "p95": 0, "p99": 0, "mean": 0, "max": 0}

    sorted_latencies = sorted(latencies)
    return {
        "p50": round(np.percentile(sorted_latencies, 50), 3),
        "p95": round(np.percentile(sorted_latencies, 95), 3),
        "p99": round(np.percentile(sorted_latencies, 99), 3),
        "mean": round(np.mean(latencies), 3),
        "max": round(max(latencies), 3),
        "min": round(min(latencies), 3)
    }


def create_confusion_matrix_data(all_matches: List[Dict], all_fps: List[Dict], all_fns: List[Dict]) -> Dict:
    """
    Create data for confusion matrix visualization.

    Args:
        all_matches: True positive matches
        all_fps: False positives
        all_fns: False negatives

    Returns:
        Dictionary with confusion matrix data
    """
    # Count entity types
    detected_types = {}
    missed_types = {}

    for match in all_matches:
        entity_type = match["ground_truth"]["type"]
        detected_types[entity_type] = detected_types.get(entity_type, 0) + 1

    for fn in all_fns:
        entity_type = fn["type"]
        missed_types[entity_type] = missed_types.get(entity_type, 0) + 1

    all_types = sorted(set(list(detected_types.keys()) + list(missed_types.keys())))

    matrix_data = []
    for entity_type in all_types:
        matrix_data.append({
            "type": entity_type,
            "detected": detected_types.get(entity_type, 0),
            "missed": missed_types.get(entity_type, 0),
            "total": detected_types.get(entity_type, 0) + missed_types.get(entity_type, 0)
        })

    return {
        "types": all_types,
        "data": matrix_data
    }


if __name__ == "__main__":
    # Test metrics calculation
    print("=== Testing Metrics Calculation ===\n")

    # Example predictions and ground truth
    predictions = [
        {"start": 14, "end": 35, "text": "[REDACTED_a1b2]", "score": 0.95},
        {"start": 50, "end": 64, "text": "[REDACTED_c3d4]", "score": 0.82}
    ]

    ground_truth = [
        {"type": "EMAIL_ADDRESS", "start": 14, "end": 35, "text": "john@example.com"},
        {"type": "PHONE_NUMBER", "start": 50, "end": 64, "text": "555-123-4567"}
    ]

    tp, fp, fn = match_entities(predictions, ground_truth)

    print(f"True Positives: {len(tp)}")
    print(f"False Positives: {len(fp)}")
    print(f"False Negatives: {len(fn)}")

    metrics = calculate_metrics(len(tp), len(fp), len(fn))
    print(f"\nMetrics: {metrics}")

    # Test latency metrics
    latencies = [0.5, 0.8, 1.2, 0.9, 1.5, 2.1, 0.7, 1.0, 0.6, 1.8]
    latency_metrics = calculate_latency_metrics(latencies)
    print(f"\nLatency Metrics: {latency_metrics}")
