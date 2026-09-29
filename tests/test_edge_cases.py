"""Edge case and false positive/negative analysis tests."""

import pytest

from maternal_reliability.baseline.simple_scorer import run_baseline_batch
from maternal_reliability.data.generator import generate_patient_readings, generate_simulated_dataset
from maternal_reliability.pipeline.orchestrator import assess_patient, run_pipeline


@pytest.mark.parametrize("scenario,patient_id", [
    ("multi_week_outage", "P003"),
    ("manual_device_conflict", "P004"),
    ("sensor_malfunction", "P005"),
])
def test_edge_cases_no_false_alert(scenario, patient_id):
    df = generate_patient_readings(patient_id, scenario, days=42, seed=1)
    assessment = assess_patient(df, patient_id, "systolic_bp")
    assert assessment.decision.alert is False, f"{scenario} should not produce actionable alert"


def test_false_positive_analysis():
    """Enhanced scorer should have fewer false positives than baseline on alert decision."""
    readings, labels = generate_simulated_dataset(seed=42)
    pipeline = run_pipeline(readings)
    baseline = run_baseline_batch(readings)
    gt = labels.set_index("patient_id")

    enhanced_fp = sum(
        1 for a in pipeline.assessments
        if a.decision.alert
        and not (gt.loc[a.patient_id, "ground_truth_alert"] and gt.loc[a.patient_id, "ground_truth_reliable"])
    )
    baseline_fp = sum(
        1 for b in baseline
        if b.alert and not gt.loc[b.patient_id, "ground_truth_alert"]
    )
    assert enhanced_fp <= baseline_fp


def test_false_negative_analysis():
    """Enhanced scorer should detect true alerts for reliable concerning trends."""
    readings, labels = generate_simulated_dataset(seed=42)
    pipeline = run_pipeline(readings)
    gt = labels.set_index("patient_id")

    for a in pipeline.assessments:
        pid = a.patient_id
        if gt.loc[pid, "ground_truth_alert"] and gt.loc[pid, "ground_truth_reliable"]:
            assert a.trend.concerning is True
            assert a.decision.alert is True or a.decision.outcome.value == "actionable"
