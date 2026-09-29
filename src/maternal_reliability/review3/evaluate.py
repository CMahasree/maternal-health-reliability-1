"""Review 3 comprehensive evaluation engine.

Evaluates data-reliability scoring, clinical alerting, uncertainty quantification,
harm mitigation, edge-case resilience, and multi-biometric monitoring on the expanded
200-profile cohort.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from maternal_reliability.baseline.simple_scorer import baseline_score
from maternal_reliability.config import OPERATIONAL_LIMITS, THRESHOLDS
from maternal_reliability.pipeline.orchestrator import assess_patient
from maternal_reliability.review3.cohort import generate_review3_cohort


def _calculate_prf(tp: int, fp: int, fn: int, tn: int) -> dict[str, float]:
    """Compute precision, recall, f1, and accuracy with zero-division protection."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "accuracy": round(float(accuracy), 4),
    }


def evaluate_review3(
    readings: pd.DataFrame | None = None,
    labels: pd.DataFrame | None = None,
    seed: int = 2026,
) -> dict[str, Any]:
    """
    Run full Review 3 evaluation on 200 profiles.

    Compares Baseline vs Proposed Scorer, evaluates uncertainty, harm,
    edge cases, and multi-biometric coverage.
    """
    if readings is None or labels is None:
        readings, labels = generate_review3_cohort(seed=seed)

    gt_dict = labels.set_index("patient_id").to_dict("index")
    patient_ids = labels["patient_id"].tolist()

    records = []
    # Alert decision counts
    b_tp, b_fp, b_fn, b_tn = 0, 0, 0, 0
    p_tp, p_fp, p_fn, p_tn = 0, 0, 0, 0

    # Reliability screening counts
    rel_tp, rel_fp, rel_fn, rel_tn = 0, 0, 0, 0

    harm_scores = []
    confidences = []
    decision_counts = {}
    fallback_frequencies = {}

    for pid in patient_ids:
        gt = gt_dict[pid]
        true_reliable = bool(gt["ground_truth_reliable"])
        true_alert = bool(gt["ground_truth_alert"])
        scenario = gt["scenario"]

        # Run Baseline Scorer (naive: missingness <= 20% + uncleaned trend)
        b_res = baseline_score(readings, pid, "systolic_bp")

        # Run Proposed Reliability Scorer (Review 1 multi-factor pipeline)
        assessment = assess_patient(readings, pid, "systolic_bp")

        score = assessment.reliability.score
        pred_reliable = (score >= THRESHOLDS.actionable_min)  # >= 70
        pred_alert = assessment.decision.alert
        outcome = assessment.decision.outcome.value

        conf = assessment.uncertainty.confidence
        harm = assessment.harm.total_harm_score

        harm_scores.append(harm)
        confidences.append(conf)
        decision_counts[outcome] = decision_counts.get(outcome, 0) + 1

        for act in assessment.decision.fallback_actions:
            fallback_frequencies[act] = fallback_frequencies.get(act, 0) + 1

        # 1. Data-Reliability Screening Confusion
        # True Positive (Reliability): True reliable correctly classified as reliable (score >= 70)
        # False Positive (Reliability): Unreliable data incorrectly accepted as reliable (score >= 70)
        # False Negative (Reliability): Reliable data incorrectly rejected (score < 70)
        # True Negative (Reliability): Unreliable data correctly rejected (score < 70)
        if true_reliable and pred_reliable:
            rel_tp += 1
        elif not true_reliable and pred_reliable:
            rel_fp += 1
        elif true_reliable and not pred_reliable:
            rel_fn += 1
        else:
            rel_tn += 1

        # 2. Clinical Alerting Confusion (Baseline vs Proposed)
        # A true alert is warranted ONLY when the patient has a true clinical escalation AND data is reliable
        warranted_alert = true_alert and true_reliable

        # Baseline confusion
        if b_res.alert and warranted_alert:
            b_tp += 1
        elif b_res.alert and not warranted_alert:
            b_fp += 1
        elif not b_res.alert and warranted_alert:
            b_fn += 1
        else:
            b_tn += 1

        # Proposed scorer confusion
        if pred_alert and warranted_alert:
            p_tp += 1
        elif pred_alert and not warranted_alert:
            p_fp += 1
        elif not pred_alert and warranted_alert:
            p_fn += 1
        else:
            p_tn += 1

        records.append({
            "patient_id": pid,
            "scenario": scenario,
            "ground_truth_reliable": true_reliable,
            "ground_truth_alert": true_alert,
            "warranted_alert": warranted_alert,
            "baseline_alert": b_res.alert,
            "baseline_missing_rate": b_res.missing_rate,
            "baseline_reason": b_res.reason,
            "reliability_score": score,
            "reliability_label": assessment.reliability.label.value,
            "pred_reliable": pred_reliable,
            "trend_concerning": assessment.trend.concerning,
            "trend_direction": assessment.trend.direction,
            "trend_slope": assessment.trend.slope_per_day,
            "trend_p_value": assessment.trend.p_value,
            "confidence": conf,
            "harm_score": harm,
            "decision": outcome,
            "proposed_alert": pred_alert,
            "rationale": "; ".join(assessment.reliability.rationale),
            "fallback_actions": assessment.decision.fallback_actions,
            "evidence_summary": assessment.evidence.summary,
        })

    eval_df = pd.DataFrame(records)

    # Compile performance metrics
    reliability_metrics = _calculate_prf(rel_tp, rel_fp, rel_fn, rel_tn)
    baseline_alert_metrics = _calculate_prf(b_tp, b_fp, b_fn, b_tn)
    proposed_alert_metrics = _calculate_prf(p_tp, p_fp, p_fn, p_tn)

    # Uncertainty distribution analysis
    conf_series = eval_df["confidence"]
    rel_conf = eval_df[eval_df["ground_truth_reliable"]]["confidence"]
    unrel_conf = eval_df[~eval_df["ground_truth_reliable"]]["confidence"]

    uncertainty_analysis = {
        "mean_confidence_all": round(float(conf_series.mean()), 2),
        "mean_confidence_reliable": round(float(rel_conf.mean()), 2),
        "mean_confidence_unreliable": round(float(unrel_conf.mean()), 2),
        "high_confidence_count": int((conf_series >= 75).sum()),
        "moderate_confidence_count": int(((conf_series >= 50) & (conf_series < 75)).sum()),
        "low_confidence_count": int((conf_series < 50).sum()),
    }

    # Error analysis: identify FP and FN cases
    fp_cases = eval_df[eval_df["proposed_alert"] & ~eval_df["warranted_alert"]].to_dict("records")
    fn_cases = eval_df[~eval_df["proposed_alert"] & eval_df["warranted_alert"]].to_dict("records")

    # Baseline FP cases (for comparison)
    baseline_fp_cases = eval_df[eval_df["baseline_alert"] & ~eval_df["warranted_alert"]].to_dict("records")

    # Per-scenario breakdown
    scenario_breakdown = {}
    for sc, grp in eval_df.groupby("scenario"):
        scenario_breakdown[sc] = {
            "n": len(grp),
            "ground_truth_reliable": bool(grp["ground_truth_reliable"].iloc[0]),
            "ground_truth_alert": bool(grp["ground_truth_alert"].iloc[0]),
            "mean_reliability_score": round(float(grp["reliability_score"].mean()), 1),
            "mean_confidence": round(float(grp["confidence"].mean()), 1),
            "proposed_alerts": int(grp["proposed_alert"].sum()),
            "baseline_alerts": int(grp["baseline_alert"].sum()),
            "decisions": grp["decision"].value_counts().to_dict(),
        }

    return {
        "cohort_n": len(patient_ids),
        "readings_n": len(readings),
        "seed": seed,
        "reliability_screening": {
            "unreliable_trends_before_screening": int((~eval_df["ground_truth_reliable"]).sum()),
            "unreliable_trends_identified": int((eval_df["reliability_score"] < THRESHOLDS.actionable_min).sum()),
            "reliable_trends_incorrectly_rejected": rel_fn,
            "unreliable_trends_incorrectly_accepted": rel_fp,
            "metrics": reliability_metrics,
        },
        "alert_comparison": {
            "baseline": baseline_alert_metrics,
            "proposed_scorer": proposed_alert_metrics,
            "fp_reduction": baseline_alert_metrics["false_positives"] - proposed_alert_metrics["false_positives"],
        },
        "uncertainty": uncertainty_analysis,
        "harm_mitigation": {
            "total_harm_score_sum": round(float(eval_df["harm_score"].sum()), 2),
            "mean_harm_score": round(float(eval_df["harm_score"].mean()), 2),
            "mean_harm_unreliable": round(float(eval_df[~eval_df["ground_truth_reliable"]]["harm_score"].mean()), 2),
        },
        "decisions": decision_counts,
        "fallback_actions": fallback_frequencies,
        "scenario_breakdown": scenario_breakdown,
        "error_cases": {
            "proposed_fp_count": len(fp_cases),
            "proposed_fn_count": len(fn_cases),
            "baseline_fp_count": len(baseline_fp_cases),
            "proposed_fp": fp_cases,
            "proposed_fn": fn_cases,
        },
        "predictions_table": records,
    }


def evaluate_multibiometric(
    readings: pd.DataFrame,
    patient_ids: list[str] | None = None,
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    """
    Evaluate reliability and trend detection across multiple biometrics.

    Covers: systolic_bp, diastolic_bp, heart_rate, blood_glucose_mgdl, weight_kg.
    """
    if metrics is None:
        metrics = ["systolic_bp", "diastolic_bp", "heart_rate", "blood_glucose_mgdl", "weight_kg"]

    if patient_ids is None:
        patient_ids = readings["patient_id"].unique()[:50].tolist()  # Sample 50 for multi-biometric matrix

    results = {}
    for m in metrics:
        scores = []
        concerning_count = 0
        slopes = []
        actionable_count = 0
        for pid in patient_ids:
            try:
                res = assess_patient(readings, pid, m)
                scores.append(res.reliability.score)
                if res.trend.concerning:
                    concerning_count += 1
                slopes.append(res.trend.slope_per_day)
                if res.decision.alert:
                    actionable_count += 1
            except Exception:
                pass

        results[m] = {
            "evaluated_patients": len(scores),
            "mean_reliability_score": round(float(np.mean(scores)), 1) if scores else 0.0,
            "min_reliability_score": round(float(np.min(scores)), 1) if scores else 0.0,
            "max_reliability_score": round(float(np.max(scores)), 1) if scores else 0.0,
            "concerning_trend_count": concerning_count,
            "actionable_alert_count": actionable_count,
            "mean_slope": round(float(np.mean(slopes)), 3) if slopes else 0.0,
        }

    return results
