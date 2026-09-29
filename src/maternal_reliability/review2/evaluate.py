"""Run Review 2 cohort evaluation. Review 1 experiments remain in run_experiments.py."""

from __future__ import annotations

import time

import pandas as pd

from maternal_reliability.data.generator import generate_simulated_dataset
from maternal_reliability.pipeline.orchestrator import assess_patient
from maternal_reliability.review2.benchmarks import (
    benchmark_callable,
    benchmark_scoring,
    connectivity_impact,
    process_cpu_seconds,
)
from maternal_reliability.review2.cohort import COHORT_N, generate_review2_cohort
from maternal_reliability.review2.metrics import (
    accuracy,
    confusion,
    f1_from_precision_recall,
    macro_f1,
    per_class_scores,
    subgroup_metrics,
)
from maternal_reliability.review2.risk_scorer import score_risk

CLINICAL_LABELS = ["low", "medium", "high"]


def _safety_label(row: pd.Series) -> str:
    if row["category"] in ("missing_data", "noisy_data", "corner_case"):
        return "indeterminate"
    return str(row["ground_truth_risk"])


def evaluate_review2(seed: int = 2026) -> dict:
    readings, labels = generate_review2_cohort(seed=seed)
    rows = []
    t0 = time.perf_counter()
    cpu0 = process_cpu_seconds()
    for rec in labels.to_dict("records"):
        result = score_risk(readings, rec["patient_id"])
        rows.append(
            {
                "patient_id": rec["patient_id"],
                "scenario": rec["scenario"],
                "category": rec["category"],
                "corner_case": rec["corner_case"],
                "y_true": rec["ground_truth_risk"],
                "y_true_safety": _safety_label(pd.Series(rec)),
                "y_pred": result.predicted_risk,
                "reliability_score": result.reliability_score,
                "reliability_gated": result.reliability_gated,
                "alert": result.alert,
                "risk_points": result.risk_points,
                "rationale": result.rationale,
            }
        )
    scoring_s = max(0.0, time.perf_counter() - t0)
    scoring_cpu_s = max(0.0, process_cpu_seconds() - cpu0)

    y_true = [r["y_true"] for r in rows]
    y_pred = [r["y_pred"] for r in rows]
    y_true_s = [r["y_true_safety"] for r in rows]

    clinical_scores = per_class_scores(y_true, y_pred, CLINICAL_LABELS)
    # Indeterminate predictions are misses for clinical classes.
    overall = {
        "n_profiles": len(rows),
        "accuracy_clinical_3class": round(accuracy(y_true, y_pred), 4),
        "macro_f1_clinical": round(macro_f1(clinical_scores), 4),
        "accuracy_safety_aware": round(accuracy(y_true_s, y_pred), 4),
        "scores_clinical": clinical_scores,
        "scores_4class": per_class_scores(y_true_s, y_pred),
        "confusion_clinical": confusion(y_true, y_pred, CLINICAL_LABELS + ["indeterminate"]),
        "confusion_safety": confusion(y_true_s, y_pred),
        "scoring_wall_clock_s": round(scoring_s, 4),
        "scoring_cpu_s": round(scoring_cpu_s, 4),
    }

    by_category = subgroup_metrics(
        [{"y_true": r["y_true"], "y_pred": r["y_pred"], "category": r["category"]} for r in rows],
        "category",
    )
    by_scenario = subgroup_metrics(
        [{"y_true": r["y_true"], "y_pred": r["y_pred"], "scenario": r["scenario"]} for r in rows],
        "scenario",
    )

    ids = labels["patient_id"].tolist()
    bench = benchmark_scoring(readings, ids, repeats=1)
    conn = connectivity_impact(readings, ids)

    return {
        "seed": seed,
        "cohort_n": COHORT_N,
        "overall": overall,
        "by_category": by_category,
        "by_scenario": by_scenario,
        "rows": rows,
        "device_benchmarks": bench,
        "connectivity": conn,
        "n_readings": int(len(readings)),
    }


def review1_baseline_snapshot(seed: int = 42) -> dict:
    """Re-run the original 8-profile pipeline. Does not reuse a 99.1% headline."""
    readings, labels = generate_simulated_dataset(seed=seed)
    snapshot = []
    tp = fp = fn = tn = 0
    for rec in labels.to_dict("records"):
        a = assess_patient(readings, rec["patient_id"], "systolic_bp")
        risk = score_risk(readings, rec["patient_id"])
        true_alert = bool(rec["ground_truth_alert"]) and bool(rec["ground_truth_reliable"])
        pred_alert = bool(a.decision.alert)
        if pred_alert and true_alert:
            tp += 1
        elif pred_alert and not true_alert:
            fp += 1
        elif not pred_alert and true_alert:
            fn += 1
        else:
            tn += 1
        snapshot.append(
            {
                "patient_id": rec["patient_id"],
                "scenario": rec["scenario"],
                "ground_truth_alert": rec["ground_truth_alert"],
                "ground_truth_reliable": rec["ground_truth_reliable"],
                "review1_alert": pred_alert,
                "review1_decision": a.decision.outcome.value,
                "review1_reliability": a.reliability.score,
                "review2_risk": risk.predicted_risk,
                "review2_gated": risk.reliability_gated,
            }
        )
    n = tp + fp + fn + tn
    acc = (tp + tn) / n if n else 0.0
    precision = round(tp / (tp + fp), 4) if (tp + fp) else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) else 0.0
    ids = labels["patient_id"].tolist()
    device = benchmark_callable(
        lambda pid: assess_patient(readings, pid, "systolic_bp"),
        ids,
        repeats=1,
    )
    return {
        "n_profiles": n,
        "metric": "alert_on_reliable_concerning_systolic_trend",
        "accuracy": round(acc, 4),
        "precision": precision,
        "recall": recall,
        "f1": round(f1_from_precision_recall(precision, recall), 4),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "device_benchmarks": device,
        "connectivity": {
            "measured": False,
            "note": (
                "Review 1 did not run a separated online / intermittent / offline scoring "
                "ablation. Connectivity is part of the reliability score, not a Review 1 "
                "headline metric."
            ),
        },
        "note": (
            "Review 1 headline accuracy on 8 simulated profiles. Any 99.1% figure from a "
            "small-n demo does not carry into Review 2."
        ),
        "profiles": snapshot,
    }


def build_side_by_side_comparison(review1: dict, review2: dict) -> dict:
    """Table of measured Review 1 vs Review 2 values. Tasks differ unless noted."""
    r1b = review1.get("device_benchmarks") or {}
    r2b = review2.get("device_benchmarks") or {}
    r2c = review2.get("connectivity") or {}
    r2o = review2["overall"]
    high = r2o["scores_clinical"]["high"]

    def row(metric, r1, r2, comparable: bool, note: str) -> dict:
        return {
            "metric": metric,
            "review1": r1,
            "review2": r2,
            "directly_comparable": comparable,
            "note": note,
        }

    rows = [
        row(
            "sample_size",
            review1["n_profiles"],
            r2o["n_profiles"],
            False,
            "Review 1 evaluated 8 hand-built scenarios; Review 2 evaluated an expanded cohort of 180 simulated profiles across 10 clinical and edge-case scenarios.",
        ),
        row(
            "accuracy",
            review1["accuracy"],
            r2o["accuracy_clinical_3class"],
            False,
            "Review 1 is binary alert-on-reliable-systolic-trend; Review 2 is 3-class clinical risk (indeterminate counts as a miss).",
        ),
        row(
            "precision",
            review1["precision"],
            high["precision"],
            False,
            "Review 1 precision is for the binary alert class; Review 2 is high-risk class precision.",
        ),
        row(
            "recall",
            review1["recall"],
            high["recall"],
            False,
            "Review 1 recall is for the binary alert class; Review 2 is high-risk class recall.",
        ),
        row(
            "f1",
            review1.get("f1"),
            high["f1"],
            False,
            "Review 1 F1 is the binary alert harmonic mean; Review 2 is high-risk F1. Macro-F1 (low/medium/high) is Review 2 only.",
        ),
        row(
            "macro_f1_clinical",
            None,
            r2o["macro_f1_clinical"],
            False,
            "Review 2 only: unweighted harmonic mean across low, medium, and high clinical risk classes. Review 1 had no 3-class macro-F1.",
        ),
        row(
            "mean_latency_ms",
            r1b.get("mean_latency_ms"),
            r2b.get("mean_latency_ms"),
            False,
            "Both measured on benchmark hardware: Review 1 times assess_patient (single-metric systolic reliability pipeline) and Review 2 times score_risk (9-biometric screening).",
        ),
        row(
            "p95_latency_ms",
            r1b.get("p95_latency_ms"),
            r2b.get("p95_latency_ms"),
            False,
            "95th percentile per-patient latency on benchmark hardware.",
        ),
        row(
            "peak_traced_ram_mb",
            r1b.get("peak_traced_ram_mb"),
            r2b.get("peak_traced_ram_mb"),
            False,
            "Peak heap memory allocation traced via tracemalloc; workloads differ (8 vs 180 profiles; different functions).",
        ),
        row(
            "process_rss_mb",
            r1b.get("process_rss_mb"),
            r2b.get("process_rss_mb"),
            False,
            "Process resident set size (working set) in MB measured via OS process API during execution.",
        ),
        row(
            "cpu_time_s",
            r1b.get("cpu_time_s"),
            r2b.get("cpu_time_s"),
            False,
            "Measured process CPU seconds (user + kernel) consumed during each benchmark loop; not comparable across different n and functions.",
        ),
        row(
            "cpu_percent",
            r1b.get("cpu_percent"),
            r2b.get("cpu_percent"),
            False,
            "Single-core CPU utilization percentage during benchmark execution (cpu_time / wall_time * 100).",
        ),
        row(
            "connectivity_online_label_change_rate_vs_full",
            None,
            (r2c.get("online_baseline") or {}).get("vs_full_mixed", {}).get("label_change_rate"),
            False,
            "Review 1 has no separated connectivity ablation. Review 2: online-only live sync slice vs full mixed store.",
        ),
        row(
            "connectivity_intermittent_label_change_rate_vs_online",
            None,
            (r2c.get("intermittent") or {}).get("vs_online_baseline", {}).get("label_change_rate"),
            False,
            "Review 2 only: intermittent-only delivery slice vs online baseline.",
        ),
        row(
            "connectivity_offline_label_change_rate_vs_online",
            None,
            (r2c.get("offline") or {}).get("vs_online_baseline", {}).get("label_change_rate"),
            False,
            "Review 2 only: offline-only local cache slice vs online baseline.",
        ),
    ]
    return {
        "tasks": {
            "review1": review1["metric"],
            "review2": "3-class plus indeterminate maternal risk on the Review 2 cohort",
        },
        "rows": rows,
    }
