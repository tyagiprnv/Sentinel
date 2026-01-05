"""
Baseline comparison: Compare Presidio vs simple regex-based PII detection.

This demonstrates the improvement of ML-based detection over rule-based approaches.
"""
import re
from typing import List, Dict


class RegexBaseline:
    """Simple regex-based PII detector as baseline for comparison."""

    def __init__(self):
        self.patterns = {
            "EMAIL_ADDRESS": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "PHONE_NUMBER": r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b',
            "US_SSN": r'\b\d{3}-\d{2}-\d{4}\b',
            "PERSON": r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # Very simple: FirstName LastName
            "IP_ADDRESS": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        }

    def detect(self, text: str) -> List[Dict]:
        """
        Detect PII entities using regex patterns.

        Args:
            text: Input text

        Returns:
            List of detected entities
        """
        entities = []

        for entity_type, pattern in self.patterns.items():
            for match in re.finditer(pattern, text):
                entities.append({
                    "type": entity_type,
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(),
                    "score": 1.0  # Regex matches are binary
                })

        # Sort by start position
        entities.sort(key=lambda x: x["start"])
        return entities


def compare_detectors(presidio_results: Dict, test_cases: List[Dict]) -> Dict:
    """
    Compare Presidio results against regex baseline.

    Args:
        presidio_results: Results from Presidio-based evaluation
        test_cases: Benchmark test cases

    Returns:
        Comparison metrics
    """
    baseline = RegexBaseline()

    baseline_tp = 0
    baseline_fp = 0
    baseline_fn = 0

    for case in test_cases:
        text = case["text"]
        ground_truth = case["ground_truth"]

        # Get baseline predictions
        predictions = baseline.detect(text)

        # Simple matching: check if predicted text overlaps with ground truth
        matched_gt = set()

        for pred in predictions:
            pred_text = pred["text"].lower()
            matched = False

            for idx, gt in enumerate(ground_truth):
                if idx in matched_gt:
                    continue

                gt_text = gt["text"].lower()

                # Check for overlap
                if (pred_text in gt_text or gt_text in pred_text or
                    pred["start"] <= gt["start"] < pred["end"] or
                    pred["start"] < gt["end"] <= pred["end"]):
                    baseline_tp += 1
                    matched_gt.add(idx)
                    matched = True
                    break

            if not matched:
                baseline_fp += 1

        # Unmatched ground truth = false negatives
        baseline_fn += (len(ground_truth) - len(matched_gt))

    # Calculate baseline metrics
    baseline_precision = baseline_tp / (baseline_tp + baseline_fp) if (baseline_tp + baseline_fp) > 0 else 0
    baseline_recall = baseline_tp / (baseline_tp + baseline_fn) if (baseline_tp + baseline_fn) > 0 else 0
    baseline_f1 = 2 * (baseline_precision * baseline_recall) / (baseline_precision + baseline_recall) if (baseline_precision + baseline_recall) > 0 else 0

    # Get Presidio metrics from results
    presidio_metrics = presidio_results.get("overall_metrics", {})

    return {
        "baseline": {
            "name": "Regex-Only",
            "precision": round(baseline_precision, 4),
            "recall": round(baseline_recall, 4),
            "f1": round(baseline_f1, 4),
            "tp": baseline_tp,
            "fp": baseline_fp,
            "fn": baseline_fn
        },
        "presidio": {
            "name": "Presidio (NLP-based)",
            "precision": presidio_metrics.get("precision", 0),
            "recall": presidio_metrics.get("recall", 0),
            "f1": presidio_metrics.get("f1", 0),
            "tp": presidio_metrics.get("true_positives", 0),
            "fp": presidio_metrics.get("false_positives", 0),
            "fn": presidio_metrics.get("false_negatives", 0)
        },
        "improvement": {
            "precision_delta": round(presidio_metrics.get("precision", 0) - baseline_precision, 4),
            "recall_delta": round(presidio_metrics.get("recall", 0) - baseline_recall, 4),
            "f1_delta": round(presidio_metrics.get("f1", 0) - baseline_f1, 4),
            "f1_improvement_pct": round(((presidio_metrics.get("f1", 0) - baseline_f1) / baseline_f1 * 100) if baseline_f1 > 0 else 0, 1)
        }
    }


def print_comparison(comparison: Dict):
    """Print formatted comparison results."""
    print("=" * 70)
    print("BASELINE COMPARISON: Regex vs Presidio")
    print("=" * 70)
    print()

    print(f"{'Metric':<20} {'Regex-Only':<15} {'Presidio':<15} {'Delta':<15}")
    print("-" * 70)

    baseline = comparison["baseline"]
    presidio = comparison["presidio"]
    improvement = comparison["improvement"]

    print(f"{'Precision':<20} {baseline['precision']:<15.2%} {presidio['precision']:<15.2%} {improvement['precision_delta']:>+14.2%}")
    print(f"{'Recall':<20} {baseline['recall']:<15.2%} {presidio['recall']:<15.2%} {improvement['recall_delta']:>+14.2%}")
    print(f"{'F1 Score':<20} {baseline['f1']:<15.2%} {presidio['f1']:<15.2%} {improvement['f1_delta']:>+14.2%}")

    print()
    print(f"Overall F1 Improvement: {improvement['f1_improvement_pct']:+.1f}%")
    print()

    print("Detection Counts:")
    print(f"  Regex:    TP={baseline['tp']}, FP={baseline['fp']}, FN={baseline['fn']}")
    print(f"  Presidio: TP={presidio['tp']}, FP={presidio['fp']}, FN={presidio['fn']}")
    print()


if __name__ == "__main__":
    # Test regex baseline
    baseline = RegexBaseline()

    test_texts = [
        "Contact john.doe@example.com",
        "Call 555-123-4567",
        "Jane Smith works here",
        "IP: 192.168.1.1"
    ]

    print("Testing Regex Baseline:")
    print()
    for text in test_texts:
        entities = baseline.detect(text)
        print(f"Text: {text}")
        print(f"Detected: {len(entities)} entities")
        for e in entities:
            print(f"  - {e['type']}: {e['text']}")
        print()
