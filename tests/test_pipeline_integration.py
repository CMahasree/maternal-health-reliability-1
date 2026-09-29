"""Integration tests for full pipeline."""

from maternal_reliability.baseline.simple_scorer import baseline_score
from maternal_reliability.data.generator import generate_simulated_dataset
from maternal_reliability.pipeline.orchestrator import assess_patient, run_pipeline


def test_full_pipeline_runs():
    readings, _ = generate_simulated_dataset(seed=42)
    result = run_pipeline(readings)
    assert len(result.assessments) > 0
    assert all(a.decision.outcome is not None for a in result.assessments)


def test_safe_fallback_on_outage():
    readings, _ = generate_simulated_dataset(seed=42)
    assessment = assess_patient(readings, "P003", "systolic_bp")
    assert assessment.decision.outcome.value in ("safe_fallback", "caution", "not_actionable")
    assert assessment.decision.alert is False


def test_actionable_on_reliable_trend():
    readings, _ = generate_simulated_dataset(seed=42)
    assessment = assess_patient(readings, "P002", "systolic_bp")
    assert assessment.reliability.score >= 50
    assert assessment.trend.concerning is True


def test_baseline_vs_enhanced_differ_on_malfunction():
    readings, _ = generate_simulated_dataset(seed=42)
    baseline = baseline_score(readings, "P005", "systolic_bp")
    enhanced = assess_patient(readings, "P005", "systolic_bp")
    # Enhanced should be more conservative (no alert or lower confidence)
    if baseline.alert:
        assert enhanced.decision.alert is False or enhanced.reliability.score < 70


def test_evidence_chain_populated():
    readings, _ = generate_simulated_dataset(seed=42)
    assessment = assess_patient(readings, "P001", "systolic_bp")
    assert assessment.evidence.summary != ""
    assert assessment.evidence.score_breakdown != {}
