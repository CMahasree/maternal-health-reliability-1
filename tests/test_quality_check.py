"""Tests for quality check module."""

import pandas as pd
import pytest

from maternal_reliability.data.generator import generate_patient_readings
from maternal_reliability.data.schema import validate_dataframe
from maternal_reliability.pipeline.quality_check import check_quality


@pytest.fixture
def stable_readings():
    return generate_patient_readings("P001", "stable_normal", days=30, seed=1)


@pytest.fixture
def outage_readings():
    return generate_patient_readings("P003", "multi_week_outage", days=42, seed=1)


def test_check_quality_stable(stable_readings):
    report = check_quality(stable_readings, "P001", "systolic_bp")
    assert report.n_readings > 0
    assert report.missing_rate < 0.3
    assert not report.source_conflict


def test_check_quality_outage(outage_readings):
    report = check_quality(outage_readings, "P003", "systolic_bp")
    assert report.n_gaps >= 0
    assert report.missing_rate > 0.1


def test_check_quality_empty():
    df = pd.DataFrame(columns=["patient_id", "timestamp", "metric", "value", "source"])
    report = check_quality(df, "PX", "systolic_bp")
    assert report.n_readings == 0
    assert report.missing_rate == 1.0


def test_validate_malformed_timestamps():
    df = pd.DataFrame({
        "patient_id": ["P1", "P1"],
        "timestamp": ["2025-01-01", "not-a-date"],
        "metric": ["systolic_bp", "systolic_bp"],
        "value": [120, 122],
        "source": ["device", "device"],
    })
    cleaned, warnings = validate_dataframe(df)
    assert len(cleaned) == 1
    assert any("malformed" in w.lower() for w in warnings)


def test_manual_device_conflict():
    df = generate_patient_readings("P004", "manual_device_conflict", days=30, seed=1)
    report = check_quality(df, "P004", "systolic_bp")
    assert report.source_conflict is True
    assert report.conflict_details != ""


def test_sensor_step_change_detected():
    df = generate_patient_readings("P005", "sensor_malfunction", days=30, seed=1)
    report = check_quality(df, "P005", "systolic_bp")
    assert report.sensor_anomaly is True
    assert report.anomaly_details != ""


def test_gradual_trend_not_sensor_anomaly():
    df = generate_patient_readings("P002", "concerning_trend", days=42, seed=1)
    report = check_quality(df, "P002", "systolic_bp")
    assert report.sensor_anomaly is False
