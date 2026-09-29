"""Review 2 unit tests — additive; original tests remain the Review 1 contract."""

from maternal_reliability.review2.benchmarks import (
    benchmark_scoring,
    connectivity_impact,
    process_cpu_seconds,
)
from maternal_reliability.review2.cohort import COHORT_N, generate_review2_cohort, generate_review2_patient
from maternal_reliability.review2.evaluate import build_side_by_side_comparison
from maternal_reliability.review2.metrics import accuracy, per_class_scores
from maternal_reliability.review2.risk_scorer import score_risk
from maternal_reliability.review2.thresholds import SYSTOLIC_BP_MMHG, band_for_value


def test_sbp_bands():
    assert band_for_value(SYSTOLIC_BP_MMHG, 120).name == "low"
    assert band_for_value(SYSTOLIC_BP_MMHG, 150).name == "medium"
    assert band_for_value(SYSTOLIC_BP_MMHG, 170).name == "high"


def test_high_risk_profile_flags_high():
    df = generate_review2_patient("R2-H", "high_preeclampsia_range", seed=7)
    result = score_risk(df, "R2-H")
    assert result.predicted_risk in ("high", "medium")
    assert any(c.metric == "systolic_bp" for c in result.contributions)


def test_stable_profile_not_high():
    df = generate_review2_patient("R2-S", "stable_normal", seed=3)
    result = score_risk(df, "R2-S")
    assert result.predicted_risk in ("low", "indeterminate")


def test_cohort_size():
    readings, labels = generate_review2_cohort(seed=2026)
    assert COHORT_N == 180
    assert len(labels) == 180
    assert "reduced_fetal_movement" in set(labels["scenario"])
    assert "maternal_fever" in set(labels["scenario"])
    assert set(labels["ground_truth_risk"]) <= {"low", "medium", "high"}
    assert readings["metric"].nunique() >= 6
    assert {"online", "intermittent", "offline"} <= set(readings["connectivity_status"])


def test_metrics_helper():
    yt = ["low", "high", "high"]
    yp = ["low", "high", "medium"]
    assert abs(accuracy(yt, yp) - 2 / 3) < 1e-9
    scores = per_class_scores(yt, yp, ["low", "medium", "high"])
    assert scores["high"]["fn"] == 1


def test_cpu_metric_is_measured():
    df = generate_review2_patient("R2-CPU", "stable_normal", seed=11)
    bench = benchmark_scoring(df, ["R2-CPU"])
    assert bench["cpu_time_s"] >= 0
    assert bench["cpu_percent"] >= 0
    assert "cpu_metric" in bench
    assert bench["logical_cpus"] >= 1
    assert bench["cpu_percent_of_logical_cpus"] >= 0
    assert bench["process_rss_mb"] is not None
    assert bench["process_rss_mb"] > 0
    assert process_cpu_seconds() >= 0


def test_connectivity_scenarios_are_separate():
    df = generate_review2_patient("R2-NET", "stable_normal", seed=13)
    conn = connectivity_impact(df, ["R2-NET"])
    assert conn["online_baseline"]["name"] == "online_baseline"
    assert conn["intermittent"]["name"] == "intermittent"
    assert conn["offline"]["name"] == "offline"
    assert "vs_online_baseline" not in conn["online_baseline"]
    assert "vs_online_baseline" in conn["intermittent"]
    assert "vs_online_baseline" in conn["offline"]
    assert "label_changes_when_dropping_offline" not in conn


def test_side_by_side_comparison_structure():
    r1 = {
        "n_profiles": 8,
        "metric": "alert_on_reliable_concerning_systolic_trend",
        "accuracy": 1.0,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
        "device_benchmarks": {
            "mean_latency_ms": 102.0,
            "p95_latency_ms": 112.5,
            "peak_traced_ram_mb": 0.168,
            "process_rss_mb": 18.5,
            "cpu_time_s": 0.75,
            "cpu_percent": 92.0,
        },
    }
    r2 = {
        "overall": {
            "n_profiles": 180,
            "accuracy_clinical_3class": 0.9167,
            "macro_f1_clinical": 0.9069,
            "scores_clinical": {
                "high": {"precision": 0.7353, "recall": 1.0, "f1": 0.8475}
            },
        },
        "device_benchmarks": {
            "mean_latency_ms": 390.0,
            "p95_latency_ms": 780.0,
            "peak_traced_ram_mb": 0.672,
            "process_rss_mb": 22.0,
            "cpu_time_s": 38.0,
            "cpu_percent": 98.0,
        },
        "connectivity": {
            "online_baseline": {"vs_full_mixed": {"label_change_rate": 0.0167}},
            "intermittent": {"vs_online_baseline": {"label_change_rate": 0.0556}},
            "offline": {"vs_online_baseline": {"label_change_rate": 0.0611}},
        },
    }
    comp = build_side_by_side_comparison(r1, r2)
    metric_names = [row["metric"] for row in comp["rows"]]
    expected_metrics = [
        "sample_size",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "mean_latency_ms",
        "p95_latency_ms",
        "peak_traced_ram_mb",
        "process_rss_mb",
        "cpu_time_s",
        "cpu_percent",
        "connectivity_online_label_change_rate_vs_full",
        "connectivity_intermittent_label_change_rate_vs_online",
        "connectivity_offline_label_change_rate_vs_online",
    ]
    for m in expected_metrics:
        assert m in metric_names, f"Missing metric: {m}"
    for row in comp["rows"]:
        assert row["directly_comparable"] is False
        assert len(row["note"]) > 0

