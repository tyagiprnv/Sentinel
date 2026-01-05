"""
Main evaluation runner for PII redaction system.

Runs benchmark cases through the system and calculates comprehensive metrics.
"""
import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, List

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.datasets import BENCHMARK_CASES, get_statistics
from evaluation.metrics import (
    match_entities, calculate_metrics, calculate_metrics_by_type,
    calculate_latency_metrics, create_confusion_matrix_data
)
from app.service import RedactorService
import redis


def run_single_evaluation(case: Dict, redactor: RedactorService) -> Dict:
    """
    Run evaluation on a single test case.

    Args:
        case: Benchmark test case
        redactor: RedactorService instance

    Returns:
        Dictionary with evaluation results
    """
    case_id = case["id"]
    text = case["text"]
    ground_truth = case["ground_truth"]

    # Measure latency
    start_time = time.time()

    try:
        # Run redaction
        redacted_text, scores, keys = redactor.redact_and_store(text)
        latency = time.time() - start_time

        # Analyze results
        # For simplicity, we'll check if entities were detected by counting redaction tokens
        import re
        redaction_tokens = re.findall(r'\[REDACTED_[a-z0-9]+\]', redacted_text)

        # Create predictions based on redaction tokens
        # Note: This is simplified - in production we'd get exact entities from Presidio
        predictions = []
        for i, token in enumerate(redaction_tokens):
            # Find token position in redacted text
            token_match = re.search(re.escape(token), redacted_text)
            if token_match:
                predictions.append({
                    "start": token_match.start(),
                    "end": token_match.end(),
                    "text": token,
                    "score": scores[i] if i < len(scores) else 0.0
                })

        # Match predictions with ground truth
        tp, fp, fn = match_entities(predictions, ground_truth)

        # Check for leaked PII (text that should be redacted but isn't)
        leaked_entities = []
        for gt_entity in ground_truth:
            gt_text = gt_entity["text"]
            if gt_text.lower() in text.lower() and gt_text.lower() in redacted_text.lower():
                # Entity appears in both original and redacted = leak
                leaked_entities.append(gt_entity)

        return {
            "case_id": case_id,
            "success": True,
            "latency": round(latency, 3),
            "redacted_text": redacted_text,
            "predictions_count": len(predictions),
            "ground_truth_count": len(ground_truth),
            "true_positives": len(tp),
            "false_positives": len(fp),
            "false_negatives": len(fn),
            "leaked_entities": leaked_entities,
            "category": case["category"],
            "confidence_scores": scores
        }

    except Exception as e:
        return {
            "case_id": case_id,
            "success": False,
            "error": str(e),
            "latency": 0,
            "category": case["category"]
        }


def run_evaluation(verbose: bool = True) -> Dict:
    """
    Run complete evaluation on all benchmark cases.

    Args:
        verbose: Print progress

    Returns:
        Dictionary with comprehensive evaluation results
    """
    if verbose:
        print("=" * 70)
        print("PII REDACTION SYSTEM EVALUATION")
        print("=" * 70)
        print()

    # Initialize redactor
    try:
        redactor = RedactorService()
        if verbose:
            print("✓ RedactorService initialized")
            print()
    except redis.ConnectionError:
        print("✗ Redis connection failed")
        print("  Please ensure Redis is running: docker-compose up redis")
        sys.exit(1)

    # Get benchmark statistics
    stats = get_statistics()
    if verbose:
        print(f"Benchmark Dataset: {stats['total_cases']} test cases")
        print(f"  - With PII: {stats['cases_with_pii']}")
        print(f"  - Without PII: {stats['cases_without_pii']}")
        print(f"  - Total entities: {stats['total_entities']}")
        print()

    # Run evaluation on all cases
    results = []
    latencies = []
    all_tp_matches = []
    all_fp = []
    all_fn = []

    if verbose:
        print("Running evaluation...")
        print()

    for i, case in enumerate(BENCHMARK_CASES):
        result = run_single_evaluation(case, redactor)
        results.append(result)

        if result["success"]:
            latencies.append(result["latency"])

        if verbose and (i + 1) % 10 == 0:
            print(f"  Completed {i + 1}/{len(BENCHMARK_CASES)} cases...")

    if verbose:
        print(f"  Completed {len(BENCHMARK_CASES)}/{len(BENCHMARK_CASES)} cases")
        print()

    # Aggregate metrics
    total_tp = sum(r["true_positives"] for r in results if r["success"])
    total_fp = sum(r["false_positives"] for r in results if r["success"])
    total_fn = sum(r["false_negatives"] for r in results if r["success"])

    overall_metrics = calculate_metrics(total_tp, total_fp, total_fn)
    latency_metrics = calculate_latency_metrics(latencies)

    # Calculate metrics by category
    category_metrics = {}
    for category in stats["categories"].keys():
        category_cases = [r for r in results if r.get("category") == category and r["success"]]
        if category_cases:
            cat_tp = sum(r["true_positives"] for r in category_cases)
            cat_fp = sum(r["false_positives"] for r in category_cases)
            cat_fn = sum(r["false_negatives"] for r in category_cases)
            category_metrics[category] = calculate_metrics(cat_tp, cat_fp, cat_fn)

    # Calculate leak detection metrics
    total_leaked = sum(len(r.get("leaked_entities", [])) for r in results if r["success"])
    leak_rate = total_leaked / stats["total_entities"] if stats["total_entities"] > 0 else 0

    # Compile final results
    evaluation_results = {
        "timestamp": datetime.now().isoformat(),
        "dataset_statistics": stats,
        "overall_metrics": overall_metrics,
        "latency_metrics": latency_metrics,
        "category_metrics": category_metrics,
        "leak_detection": {
            "total_leaked_entities": total_leaked,
            "leak_rate": round(leak_rate, 4),
            "total_entities": stats["total_entities"]
        },
        "individual_results": results
    }

    # Print summary
    if verbose:
        print("=" * 70)
        print("EVALUATION RESULTS")
        print("=" * 70)
        print()
        print(f"Overall Performance:")
        print(f"  Precision:  {overall_metrics['precision']:.2%}")
        print(f"  Recall:     {overall_metrics['recall']:.2%}")
        print(f"  F1 Score:   {overall_metrics['f1']:.2%}")
        print()
        print(f"Detection Statistics:")
        print(f"  True Positives:  {overall_metrics['true_positives']}")
        print(f"  False Positives: {overall_metrics['false_positives']}")
        print(f"  False Negatives: {overall_metrics['false_negatives']}")
        print()
        print(f"Latency (seconds):")
        print(f"  P50:  {latency_metrics['p50']}s")
        print(f"  P95:  {latency_metrics['p95']}s")
        print(f"  P99:  {latency_metrics['p99']}s")
        print(f"  Mean: {latency_metrics['mean']}s")
        print()
        print(f"Leak Detection:")
        print(f"  Leaked entities: {total_leaked} / {stats['total_entities']}")
        print(f"  Leak rate: {leak_rate:.2%}")
        print()

        if category_metrics:
            print(f"Performance by Category:")
            for category, metrics in category_metrics.items():
                print(f"  {category}:")
                print(f"    Precision: {metrics['precision']:.2%}, Recall: {metrics['recall']:.2%}, F1: {metrics['f1']:.2%}")
            print()

    return evaluation_results


def save_results(results: Dict, output_file: str = "evaluation/results/benchmark_results.json"):
    """
    Save evaluation results to JSON file.

    Args:
        results: Evaluation results dictionary
        output_file: Output file path
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"✓ Results saved to {output_file}")
    print()


def main():
    """Main evaluation entry point."""
    print()
    results = run_evaluation(verbose=True)
    save_results(results)

    # Print summary for portfolio
    print("=" * 70)
    print("PORTFOLIO SUMMARY")
    print("=" * 70)
    print()
    print(f"📊 **Benchmark Dataset**: {results['dataset_statistics']['total_cases']} test cases")
    print(f"   - {results['dataset_statistics']['total_entities']} PII entities")
    print(f"   - {len(results['dataset_statistics']['categories'])} categories")
    print()
    print(f"🎯 **Overall Performance**:")
    metrics = results['overall_metrics']
    print(f"   - Precision: {metrics['precision']:.1%}")
    print(f"   - Recall:    {metrics['recall']:.1%}")
    print(f"   - F1 Score:  {metrics['f1']:.1%}")
    print()
    print(f"⚡ **Latency**: P95 = {results['latency_metrics']['p95']}s")
    print()
    print("💡 **Key Insights**:")
    print(f"   - {metrics['false_negatives']} entities missed (false negatives)")
    print(f"   - {metrics['false_positives']} false positives (over-redaction)")
    print(f"   - {results['leak_detection']['total_leaked_entities']} leaked entities")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
