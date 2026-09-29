"""Data schema definitions for maternal health device readings."""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

# Column definitions and dtypes for device readings
DEVICE_READINGS_SCHEMA = {
    "reading_id": "string",
    "patient_id": "string",
    "timestamp": "datetime64[ns, UTC]",
    "metric": "string",  # systolic_bp, diastolic_bp, heart_rate, weight_kg, fetal_movement
    "value": "float64",
    "source": "string",  # device | manual | health_worker
    "device_id": "string",
    "connectivity_status": "string",  # online | offline | intermittent
    "quality_label": "string",  # good | suspect | bad | missing_imputed
    "gap_before_hours": "float64",  # hours since previous reading for this metric
    "is_gap": "bool",  # True if gap_before_hours exceeds expected interval
    "notes": "string",
}

METRICS = ["systolic_bp", "diastolic_bp", "heart_rate", "weight_kg", "fetal_movement"]
# Review 2 extended biometrics (kept off the Review 1 generator loop)
REVIEW2_METRICS = METRICS + [
    "blood_glucose_mgdl",
    "hrv_rmssd_ms",
    "temperature_c",
    "spo2_pct",
]
KNOWN_METRICS = REVIEW2_METRICS
SOURCES = ["device", "manual", "health_worker"]
CONNECTIVITY = ["online", "offline", "intermittent"]
QUALITY_LABELS = ["good", "suspect", "bad", "missing_imputed"]

# Expected measurement intervals (hours) by metric in remote monitoring
EXPECTED_INTERVAL_HOURS = {
    "systolic_bp": 24.0,
    "diastolic_bp": 24.0,
    "heart_rate": 12.0,
    "weight_kg": 168.0,  # weekly
    "fetal_movement": 24.0,
    "blood_glucose_mgdl": 24.0,
    "hrv_rmssd_ms": 24.0,
    "temperature_c": 12.0,
    "spo2_pct": 12.0,
}


@dataclass
class ReadingRecord:
    """Single maternal health reading record."""

    reading_id: str
    patient_id: str
    timestamp: pd.Timestamp
    metric: str
    value: float
    source: str
    device_id: str
    connectivity_status: str
    quality_label: str
    gap_before_hours: float
    is_gap: bool
    notes: str = ""


def validate_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Validate and normalize a readings DataFrame.

    Returns cleaned DataFrame and list of validation warnings.
    """
    warnings: list[str] = []
    if df.empty:
        warnings.append("Empty dataset provided")
        return df, warnings

    required = ["patient_id", "timestamp", "metric", "value", "source"]
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    bad_ts = df["timestamp"].isna()
    if bad_ts.any():
        n = int(bad_ts.sum())
        warnings.append(f"Dropped {n} rows with malformed timestamps")
        df = df[~bad_ts]

    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    bad_val = df["value"].isna()
    if bad_val.any():
        n = int(bad_val.sum())
        warnings.append(f"Dropped {n} rows with non-numeric values")
        df = df[~bad_val]

    invalid_metrics = ~df["metric"].isin(KNOWN_METRICS)
    if invalid_metrics.any():
        n = int(invalid_metrics.sum())
        warnings.append(f"Found {n} rows with unknown metrics (kept but flagged)")

    return df.sort_values(["patient_id", "metric", "timestamp"]).reset_index(drop=True), warnings
