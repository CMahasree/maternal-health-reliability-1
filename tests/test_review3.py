"""Review 3 unit and integration tests.

Additive test suite validating the 200-profile cohort, data-reliability screening,
multi-biometric coverage, and benchmarking telemetry.
Leaves Review 1 and Review 2 tests unchanged.
"""

import pandas as pd
import pytest

from maternal_reliability.pipeline.orchestrator import assess_patient
from maternal_reliability.review3.benchmarks import benchmark_review3
from maternal_reliability.review3.cohort import (
    REVIEW3_COHORT_N,
    generate_review3_cohort,
    generate_review3_patient,
)
from maternal_reliability.review3.evaluate import evaluate_multibiometric, evaluate_review3


def test_review3_cohort_size_and_schema():
    readings, labels = generate_review3_cohort(seed=2026)
    assert len(labels) == REVIEW3_COHORT_N == 200
    assert len(readings) > 40000
    assert set(labels["scenario"].unique()) == {
        "stable_normal",
        "concerning_trend",
        "multi_week_outage",
        "manual_device_conflict",
        "sensor_malfunction",
        "irregular_timing",
        "poor_quality_noisy",
        "insufficient_data",
        "stale_data",
    }
    assert "ground_truth_reliable" in labels.columns
    assert "ground_truth_alert" in labels.columns
    assert {"online", "offline", "intermittent"} <= set(readings["connectivity_status"])
    assert {"good", "suspect"} <= set(readings["quality_label"])


def test_review3_unreliable_scenarios_rejected():
    for scenario in ["multi_week_outage", "manual_device_conflict", "sensor_malfunction"]:
        df = generate_review3_patient("R3-TEST", scenario, seed=42)
        res = assess_patient(df, "R3-TEST", "systolic_bp")
        assert res.reliability.score < 70, f"{scenario} must not exceed actionable threshold 70"
        assert res.decision.alert is False, f"{scenario} must not produce clinical alert"


def test_review3_concerning_trend_actionable():
    df = generate_review3_patient("R3-ALERT", "concerning_trend", seed=42)
    res = assess_patient(df, "R3-ALERT", "systolic_bp")
    assert res.reliability.score >= 70
    assert res.trend.concerning is True
    assert res.decision.alert is True
    assert res.decision.outcome.value == "actionable"


def test_review3_multibiometric_pipeline():
    df = generate_review3_patient("R3-BIO", "concerning_trend", seed=42)
    for metric in ["systolic_bp", "diastolic_bp", "heart_rate", "blood_glucose_mgdl", "weight_kg"]:
        res = assess_patient(df, "R3-BIO", metric)
        assert res.reliability.score > 0
        assert res.trend.direction in ("rising", "falling", "stable", "insufficient_data")


def test_review3_benchmarking_telemetry():
    df = generate_review3_patient("R3-BENCH", "stable_normal", seed=42)
    bench = benchmark_review3(df, ["R3-BENCH"], metric="systolic_bp", repeats=1)
    assert bench["execution"]["n_profiles"] == 1
    assert bench["latency_ms"]["mean"] > 0
    assert bench["resources"]["peak_traced_ram_mb"] > 0
    assert bench["environment"]["python_version"].startswith("3.")
