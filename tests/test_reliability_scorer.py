"""Tests for reliability scoring."""

import pytest

from maternal_reliability.config import ReliabilityLabel
from maternal_reliability.data.generator import generate_patient_readings
from maternal_reliability.pipeline.quality_check import check_quality
from maternal_reliability.pipeline.reliability_scorer import score_reliability


def test_high_reliability_stable():
    df = generate_patient_readings("P001", "stable_normal", days=30, seed=1)
    quality = check_quality(df, "P001", "systolic_bp")
    score = score_reliability(quality)
    assert score.score >= 70
    assert score.label in (ReliabilityLabel.HIGH, ReliabilityLabel.MODERATE)


def test_low_reliability_outage():
    df = generate_patient_readings("P003", "multi_week_outage", days=42, seed=1)
    quality = check_quality(df, "P003", "systolic_bp")
    score = score_reliability(quality)
    assert score.score < 70


def test_unreliable_sensor_malfunction():
    df = generate_patient_readings("P005", "sensor_malfunction", days=30, seed=1)
    quality = check_quality(df, "P005", "systolic_bp")
    score = score_reliability(quality)
    assert score.score < 70
    assert len(score.rationale) > 0


def test_components_sum_weighted():
    df = generate_patient_readings("P001", "stable_normal", days=20, seed=1)
    quality = check_quality(df, "P001", "heart_rate")
    score = score_reliability(quality)
    assert all(0 <= v <= 100 for v in score.components.values())
    assert "completeness" in score.components
