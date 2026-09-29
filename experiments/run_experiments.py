"""Edge case experiments and baseline comparison."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from maternal_reliability.baseline.simple_scorer import run_baseline_batch
from maternal_reliability.data.generator import generate_patient_readings, generate_simulated_dataset
from maternal_reliability.pipeline.orchestrator import assess_patient, run_pipeline


EDGE_CASES = [
    ("multi_week_outage", "P003", "18-day device outage mid-series"),
    ("manual_device_conflict", "P004", "Manual BP contradicts last device reading"),
    ("sensor_malfunction", "P005", "Sudden sensor failure with spurious high BP"),
    ("irregular_timing", "P006", "Measurement frequency change mid-series"),
]


def run_edge_case_experiments() -> list[dict]:
    """Run structured edge case evaluations."""
    results = []
    for scenario, patient_id, description in EDGE_CASES:
        df = generate_patient_readings(patient_id, scenario, seed=42)
        assessment = assess_patient(df, patient_id, "systolic_bp")
        results.append({
            "scenario": scenario,
            "patient_id": patient_id,
            "description": description,
            "reliability_score": assessment.reliability.score,
            "reliability_label": assessment.reliability.label.value,
            "trend_concerning": assessment.trend.concerning,
            "confidence": assessment.uncertainty.confidence,
            "decision": assessment.decision.outcome.value,
            "alert": assessment.decision.alert,
            "harm_score": assessment.harm.total_harm_score,
            "evidence_summary": assessment.evidence.summary,
            "fallback_actions": assessment.decision.fallback_actions,
            "rationale": assessment.reliability.rationale,
        })
    return results


def compare_baseline_vs_enhanced() -> dict:
    """Compare baseline and enhanced scorers on full simulated dataset."""
    readings, labels = generate_simulated_dataset(seed=42)
    pipeline = run_pipeline(readings)
    baseline_results = run_baseline_batch(readings)

    enhanced_alerts = {a.patient_id: a.decision.alert for a in pipeline.assessments}
    baseline_alerts = {b.patient_id: b.alert for b in baseline_results}
    gt = labels.set_index("patient_id")

    fp, fn, tp, tn = 0, 0, 0, 0
    baseline_fp, baseline_fn = 0, 0
    rows = []

    for pid in gt.index:
        true_alert = bool(gt.loc[pid, "ground_truth_alert"])
        true_reliable = bool(gt.loc[pid, "ground_truth_reliable"])
        enhanced_alert = enhanced_alerts.get(pid, False)
        baseline_alert = baseline_alerts.get(pid, False)

        if enhanced_alert and true_alert and true_reliable:
            tp += 1
        elif enhanced_alert and (not true_alert or not true_reliable):
            fp += 1
        elif not enhanced_alert and true_alert and true_reliable:
            fn += 1
        else:
            tn += 1

        if baseline_alert and (not true_alert or not true_reliable):
            baseline_fp += 1
        if not baseline_alert and true_alert and true_reliable:
            baseline_fn += 1

        rows.append({
            "patient_id": pid,
            "scenario": gt.loc[pid, "scenario"],
            "ground_truth_alert": true_alert,
            "ground_truth_reliable": true_reliable,
            "enhanced_alert": enhanced_alert,
            "baseline_alert": baseline_alert,
        })

    return {
        "comparison_table": rows,
        "enhanced": {
            "true_positives": tp, "false_positives": fp,
            "false_negatives": fn, "true_negatives": tn,
            "total_alerts": sum(enhanced_alerts.values()),
        },
        "baseline": {
            "false_positives": baseline_fp,
            "false_negatives": baseline_fn,
            "total_alerts": sum(baseline_alerts.values()),
        },
    }


def main() -> None:
    output_dir = ROOT / "experiments" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    edge_results = run_edge_case_experiments()
    comparison = compare_baseline_vs_enhanced()

    with open(output_dir / "edge_cases.json", "w") as f:
        json.dump(edge_results, f, indent=2)

    with open(output_dir / "baseline_comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)

    print("Edge Case Results:")
    for r in edge_results:
        print(f"  [{r['scenario']}] score={r['reliability_score']} decision={r['decision']} alert={r['alert']}")

    print("\nBaseline vs Enhanced:")
    print(f"  Enhanced alerts: {comparison['enhanced']['total_alerts']} "
          f"(FP={comparison['enhanced']['false_positives']}, FN={comparison['enhanced']['false_negatives']})")
    print(f"  Baseline alerts: {comparison['baseline']['total_alerts']} "
          f"(FP={comparison['baseline']['false_positives']}, FN={comparison['baseline']['false_negatives']})")
    print(f"\nResults saved to {output_dir}")


if __name__ == "__main__":
    main()
