"""Review 3 Evaluation, Benchmarking, and Reporting Runner.

Executes the expanded 200-profile evaluation, benchmarks latency and memory,
evaluates multi-biometric monitoring, generates audit artifacts, and outputs
reproducible results for the Review 3 milestone.

Leaves Review 1 and Review 2 files and outputs intact.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from maternal_reliability.pipeline.orchestrator import assess_patient
from maternal_reliability.review3.benchmarks import benchmark_review3
from maternal_reliability.review3.cohort import (
    generate_review3_cohort,
    get_cohort_summary,
    save_review3_cohort,
)
from maternal_reliability.review3.evaluate import (
    evaluate_multibiometric,
    evaluate_review3,
)


def run_structured_edge_cases(readings: pd.DataFrame) -> list[dict]:
    """Demonstrate structured edge and failure cases."""
    edge_cases = [
        ("multi_week_outage", "R3-076", "18-day device outage mid-series (offline)"),
        ("manual_device_conflict", "R3-101", "Manual cuff contradicts automated device by -24 mmHg within 48h"),
        ("sensor_malfunction", "R3-121", "Spurious sensor step-change (+35 mmHg jump)"),
        ("irregular_timing", "R3-141", "Erratic jitter (±16h) and reduced sampling frequency"),
        ("poor_quality_noisy", "R3-161", "Intermittent connectivity with >25% suspect/bad readings"),
        ("insufficient_data", "R3-176", "Sparse telemetry (<5 readings across monitoring window)"),
        ("stale_data", "R3-191", "Patient ceased reporting; latest reading >72h old"),
    ]

    results = []
    for scenario, pid, desc in edge_cases:
        assessment = assess_patient(readings, pid, "systolic_bp")
        results.append({
            "scenario": scenario,
            "patient_id": pid,
            "description": desc,
            "reliability_score": assessment.reliability.score,
            "reliability_label": assessment.reliability.label.value,
            "confidence": assessment.uncertainty.confidence,
            "decision": assessment.decision.outcome.value,
            "alert": assessment.decision.alert,
            "harm_score": assessment.harm.total_harm_score,
            "evidence_summary": assessment.evidence.summary,
            "fallback_actions": assessment.decision.fallback_actions,
            "rationale": assessment.reliability.rationale,
            "quality_warnings": assessment.quality.warnings,
        })
    return results


def generate_plots(results: dict, benchmarks: dict, multibiometric: dict, out_dir: Path) -> None:
    """Generate visual evaluation artifacts for documentation."""
    # 1. Reliability Scores and Confidence by Scenario
    scenarios = sorted(results["scenario_breakdown"].keys())
    scores = [results["scenario_breakdown"][s]["mean_reliability_score"] for s in scenarios]
    conf = [results["scenario_breakdown"][s]["mean_confidence"] for s in scenarios]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(scenarios))
    w = 0.35
    ax.bar([i - w / 2 for i in x], scores, width=w, label="Mean Reliability Score (0-100)", color="#2b5c8f")
    ax.bar([i + w / 2 for i in x], conf, width=w, label="Mean Confidence %", color="#e27c38")
    ax.axhline(70, color="green", linestyle="--", alpha=0.7, label="Actionable Threshold (>=70)")
    ax.axhline(50, color="red", linestyle="--", alpha=0.7, label="Safe Fallback Threshold (<50)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(scenarios, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("Score / Percentage")
    ax.set_title("Review 3: Reliability Score & Confidence across 9 Cohort Scenarios (n=200)")
    ax.set_ylim(0, 105)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(out_dir / "reliability_scores_by_scenario.png", dpi=140)
    plt.close(fig)

    # 2. Multi-biometric Evaluation Comparison
    bio_metrics = list(multibiometric.keys())
    bio_scores = [multibiometric[m]["mean_reliability_score"] for m in bio_metrics]
    bio_slopes = [multibiometric[m]["mean_slope"] for m in bio_metrics]

    fig, ax1 = plt.subplots(figsize=(9, 4.5))
    color = "tab:blue"
    ax1.set_xlabel("Biometric Metric")
    ax1.set_ylabel("Mean Reliability Score", color=color)
    bars = ax1.bar(bio_metrics, bio_scores, color=color, alpha=0.7, width=0.4)
    ax1.tick_params(axis="y", labelcolor=color)
    ax1.set_ylim(0, 100)
    ax1.set_title("Review 3: Multi-Biometric Reliability Scorer Evaluation")
    fig.tight_layout()
    fig.savefig(out_dir / "multibiometric_comparison.png", dpi=140)
    plt.close(fig)


def main() -> None:
    print("=" * 60)
    print("STARTING REVIEW 3 EVALUATION & BENCHMARKING PIPELINE")
    print("=" * 60)

    out_data = ROOT / "data"
    out_results = ROOT / "experiments" / "results" / "review3"
    out_results.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate & persist Review 3 expanded cohort (200 profiles)
    print("\n[1/5] Generating 200-profile reproducible Review 3 cohort...")
    r_path, l_path = save_review3_cohort(out_data, seed=2026)
    readings = pd.read_csv(r_path, parse_dates=["timestamp"])
    labels = pd.read_csv(l_path)
    summary = get_cohort_summary(readings, labels)
    print(f"      Saved {len(labels)} profiles and {len(readings)} readings to:")
    print(f"      - {r_path}")
    print(f"      - {l_path}")

    # Step 2: Run core Review 3 evaluation
    print("\n[2/5] Running Baseline vs Proposed Scorer evaluation...")
    eval_res = evaluate_review3(readings, labels, seed=2026)
    preds = eval_res.pop("predictions_table")

    # Save predictions CSV
    pred_df = pd.DataFrame(preds)
    pred_csv_path = out_results / "review3_predictions.csv"
    pred_df.to_csv(pred_csv_path, index=False)
    print(f"      Saved prediction-level audit rows to {pred_csv_path}")

    # Step 3: Run multi-biometric evaluation
    print("\n[3/5] Evaluating multi-biometric coverage...")
    pids = labels["patient_id"].tolist()
    multi_bio = evaluate_multibiometric(readings, pids[:100])
    with open(out_results / "multibiometric_results.json", "w") as f:
        json.dump(multi_bio, f, indent=2)

    # Step 4: Run latency and resource benchmarks
    print("\n[4/5] Executing quantitative latency and resource benchmarks...")
    benchmarks = benchmark_review3(readings, pids, metric="systolic_bp", repeats=1)
    with open(out_results / "benchmarks.json", "w") as f:
        json.dump(benchmarks, f, indent=2)

    # Step 5: Run structured edge case audit
    print("\n[5/5] Auditing structured edge cases and failure modes...")
    edge_results = run_structured_edge_cases(readings)
    with open(out_results / "edge_cases.json", "w") as f:
        json.dump(edge_results, f, indent=2)

    # Save metrics and baseline comparison JSON files
    with open(out_results / "review3_metrics.json", "w") as f:
        json.dump(eval_res, f, indent=2)

    baseline_comp = {
        "cohort_size": eval_res["cohort_n"],
        "unreliable_trends_before_screening": eval_res["reliability_screening"]["unreliable_trends_before_screening"],
        "unreliable_trends_identified": eval_res["reliability_screening"]["unreliable_trends_identified"],
        "reliable_trends_incorrectly_rejected": eval_res["reliability_screening"]["reliable_trends_incorrectly_rejected"],
        "unreliable_trends_incorrectly_accepted": eval_res["reliability_screening"]["unreliable_trends_incorrectly_accepted"],
        "baseline_alerts": eval_res["alert_comparison"]["baseline"],
        "proposed_scorer_alerts": eval_res["alert_comparison"]["proposed_scorer"],
        "harm_prevented": eval_res["harm_mitigation"],
    }
    with open(out_results / "baseline_vs_proposed.json", "w") as f:
        json.dump(baseline_comp, f, indent=2)

    with open(out_results / "error_analysis.json", "w") as f:
        json.dump(eval_res["error_cases"], f, indent=2)

    # Generate charts
    generate_plots(eval_res, benchmarks, multi_bio, out_results)

    print("\n" + "=" * 60)
    print("REVIEW 3 EXECUTION SUMMARY (ALL NUMBERS MEASURED)")
    print("=" * 60)
    print(f"Cohort Size:                   {eval_res['cohort_n']} profiles ({summary['n_readings']} readings)")
    print(f"Unreliable Profiles:           {eval_res['reliability_screening']['unreliable_trends_before_screening']} / 200")
    print(f"Unreliable Identified by Scorer: {eval_res['reliability_screening']['unreliable_trends_identified']} / 200")
    print(f"Reliable Trends Incorrectly Rejected (FN): {eval_res['reliability_screening']['reliable_trends_incorrectly_rejected']}")
    print(f"Unreliable Trends Incorrectly Accepted (FP): {eval_res['reliability_screening']['unreliable_trends_incorrectly_accepted']}")
    print(f"Reliability Screening F1:      {eval_res['reliability_screening']['metrics']['f1']}")
    print(f"Reliability Screening Recall:  {eval_res['reliability_screening']['metrics']['recall']}")
    print(f"Reliability Screening Precision: {eval_res['reliability_screening']['metrics']['precision']}")
    print("-" * 60)
    print(f"Alert Precision (Proposed):    {eval_res['alert_comparison']['proposed_scorer']['precision']}")
    print(f"Alert Recall (Proposed):       {eval_res['alert_comparison']['proposed_scorer']['recall']}")
    print(f"Alert F1 (Proposed):           {eval_res['alert_comparison']['proposed_scorer']['f1']}")
    print(f"Alert FP Count (Proposed):     {eval_res['alert_comparison']['proposed_scorer']['false_positives']}")
    print(f"Alert FN Count (Proposed):     {eval_res['alert_comparison']['proposed_scorer']['false_negatives']}")
    print("-" * 60)
    print(f"Mean Latency:                  {benchmarks['latency_ms']['mean']} ms/patient")
    print(f"Median Latency:                {benchmarks['latency_ms']['median']} ms/patient")
    print(f"p95 Latency:                   {benchmarks['latency_ms']['p95']} ms/patient")
    print(f"Peak Traced RAM:               {benchmarks['resources']['peak_traced_ram_mb']} MB")
    print(f"Process RSS (Working Set):     {benchmarks['resources']['process_rss_mb_after']} MB")
    print(f"Process CPU Seconds:           {benchmarks['resources']['process_cpu_seconds']} s")
    print(f"Throughput:                    {benchmarks['throughput']['profiles_per_second']} profiles/s")
    print("=" * 60)
    print(f"All artifacts saved to: {out_results}")


if __name__ == "__main__":
    main()
