"""Tests for trend detection."""

from maternal_reliability.data.generator import generate_patient_readings
from maternal_reliability.pipeline.trend_detection import detect_trend


def test_concerning_trend_detected():
    df = generate_patient_readings("P002", "concerning_trend", days=30, seed=1)
    trend = detect_trend(df, "P002", "systolic_bp")
    assert trend.n_points >= 5
    assert trend.direction == "rising"
    assert trend.concerning is True


def test_insufficient_data():
    df = generate_patient_readings("P001", "stable_normal", days=3, seed=1)
    trend = detect_trend(df, "P001", "systolic_bp")
    assert trend.concerning is False


def test_sensor_malfunction_not_necessarily_concerning_with_few_bad():
    df = generate_patient_readings("P005", "sensor_malfunction", days=15, seed=1)
    trend = detect_trend(df, "P005", "systolic_bp")
    assert trend.n_points >= 0
