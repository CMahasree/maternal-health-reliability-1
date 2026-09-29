"""Review 3 expanded 200-profile evaluation cohort generator.

This module expands the experimental evaluation to 200 profiles while preserving
the existing Review 1 (8-profile) and Review 2 (180-profile) datasets and pipelines.

Cohort size = 200 matches OPERATIONAL_LIMITS.batch_processing_max_patients.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from maternal_reliability.data.schema import (
    CONNECTIVITY,
    EXPECTED_INTERVAL_HOURS,
    QUALITY_LABELS,
    REVIEW2_METRICS,
    SOURCES,
)

# 200 profiles covering all supported real-world remote telemetry conditions
REVIEW3_COHORT_PLAN = (
    ("stable_normal", True, False, 40),          # Reliable, no alert
    ("concerning_trend", True, True, 35),        # Reliable, true clinical escalation alert
    ("multi_week_outage", False, False, 25),     # Unreliable: 18-day sensor gap
    ("manual_device_conflict", False, False, 20),# Unreliable: manual cuff contradicts device
    ("sensor_malfunction", False, False, 20),    # Unreliable: spurious +35 mmHg step-change
    ("irregular_timing", False, False, 20),      # Unreliable: erratic jitter & low frequency
    ("poor_quality_noisy", False, False, 15),    # Unreliable: >25% bad/suspect quality flags
    ("insufficient_data", False, False, 15),     # Unreliable: <5 observations in window
    ("stale_data", False, False, 10),            # Unreliable: last reading >72h ago
)

REVIEW3_COHORT_N = sum(n for _, _, _, n in REVIEW3_COHORT_PLAN)


def _base_vitals(metric: str, day: int, seed: int) -> float:
    """Generate physiological base value with slight patient-level variation."""
    rng = np.random.default_rng(seed + day)
    bases = {
        "systolic_bp": 118.0 + (seed % 8),
        "diastolic_bp": 72.0 + (seed % 6),
        "heart_rate": 76.0 + (seed % 10),
        "weight_kg": 68.0 + (day * 0.08) + (seed % 4) * 0.4,
        "fetal_movement": 10.0 + (seed % 4),
        "blood_glucose_mgdl": 88.0 + (seed % 8),
        "hrv_rmssd_ms": 32.0 + (seed % 6),
        "temperature_c": 36.7 + (seed % 3) * 0.1,
        "spo2_pct": 98.0,
    }
    noise_scales = {
        "systolic_bp": 2.5,
        "diastolic_bp": 1.8,
        "heart_rate": 3.0,
        "weight_kg": 0.15,
        "fetal_movement": 1.0,
        "blood_glucose_mgdl": 3.5,
        "hrv_rmssd_ms": 2.0,
        "temperature_c": 0.12,
        "spo2_pct": 0.5,
    }
    val = bases.get(metric, 100.0) + float(rng.normal(0, noise_scales.get(metric, 1.0)))
    if metric == "spo2_pct":
        val = min(100.0, max(85.0, val))
    if metric == "fetal_movement":
        val = max(0.0, val)
    return round(float(val), 2)


def _make_reading_record(
    patient_id: str,
    timestamp: pd.Timestamp,
    metric: str,
    value: float,
    source: str,
    connectivity: str,
    quality: str,
    prior: list[dict],
    notes: str = "",
    scenario: str = "",
) -> dict:
    gap_hours = 0.0
    is_gap = False
    same = [r for r in prior if r["metric"] == metric and r["patient_id"] == patient_id]
    if same:
        gap_hours = (timestamp - same[-1]["timestamp"]).total_seconds() / 3600.0
        expected = EXPECTED_INTERVAL_HOURS.get(metric, 24.0)
        is_gap = gap_hours > expected * 2.0

    return {
        "reading_id": str(uuid.uuid4())[:8],
        "patient_id": patient_id,
        "timestamp": timestamp,
        "metric": metric,
        "value": round(float(value), 2),
        "source": source,
        "device_id": f"DEV-{patient_id}-R3",
        "connectivity_status": connectivity,
        "quality_label": quality,
        "gap_before_hours": round(gap_hours, 1) if not np.isnan(gap_hours) else 0.0,
        "is_gap": bool(is_gap),
        "notes": notes,
        "scenario": scenario,
    }


def generate_review3_patient(
    patient_id: str,
    scenario: str,
    seed: int,
    days: int = 42,
    now: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Generate multi-biometric readings for one patient under a Review 3 scenario."""
    rng = np.random.default_rng(seed)
    if now is None:
        now = pd.Timestamp.now(tz="UTC")
    start = now - pd.Timedelta(days=days)

    records: list[dict] = []
    outage_start, outage_end = 14, 32  # 18-day outage window

    # Insufficient data scenario only generates a few isolated days
    active_days = range(days)
    if scenario == "insufficient_data":
        active_days = [2, 18, 38]  # Only 3 points over 42 days

    # Stale data scenario cuts off 5 days before 'now'
    if scenario == "stale_data":
        cutoff_day = days - 5  # Last reading is ~120h old (>72h stale threshold)
        active_days = range(max(1, cutoff_day))

    for day in active_days:
        skip_day = False
        connectivity = "online"
        quality = "good"

        # Multi-week outage drops all telemetry during outage window
        if scenario == "multi_week_outage" and outage_start <= day < outage_end:
            skip_day = True
            connectivity = "offline"

        # Irregular timing drops 60% of readings after day 15
        if scenario == "irregular_timing" and day >= 15:
            if day % 3 != 0:
                skip_day = True

        if skip_day:
            continue

        # Intermittent connectivity and noise
        if rng.random() < 0.10:
            connectivity = "intermittent"
        elif rng.random() < 0.08:
            connectivity = "offline"

        if scenario == "poor_quality_noisy":
            if rng.random() < 0.35:
                quality = "suspect" if rng.random() < 0.6 else "bad"
        elif connectivity == "intermittent" and rng.random() < 0.25:
            quality = "suspect"

        # Base timestamp with jitter
        jitter_hours = int(rng.integers(-5, 6))
        if scenario == "irregular_timing" and day >= 15:
            jitter_hours = int(rng.integers(-16, 17))

        ts_base = start + pd.Timedelta(days=day, hours=10 + jitter_hours)

        for metric in REVIEW2_METRICS:
            # Frequency subsampling for sparse metrics
            if metric == "weight_kg" and day % 7 != 0:
                continue
            if metric == "fetal_movement" and day % 2 != 0:
                continue

            val = _base_vitals(metric, day, seed)
            q = quality
            source = "device"
            notes = ""

            # Scenario 1: Concerning trend — progressive clinical rise
            if scenario == "concerning_trend" and day >= 10:
                if metric == "systolic_bp":
                    val += (day - 10) * 1.8
                elif metric == "diastolic_bp":
                    val += (day - 10) * 1.1
                elif metric == "blood_glucose_mgdl":
                    val += (day - 10) * 3.2
                elif metric == "heart_rate":
                    val += (day - 10) * 1.2
                elif metric == "weight_kg":
                    val += (day - 10) * 0.16

            # Scenario 2: Sensor malfunction — abrupt step jump after day 20
            if scenario == "sensor_malfunction" and day >= 20:
                if metric == "systolic_bp":
                    val += 35.0
                    q = "good"  # Firmware does not detect the glitch
                    notes = "Sensor step anomaly"
                elif metric == "heart_rate":
                    val += 40.0
                    q = "good"
                    notes = "Sensor step anomaly"

            # Scenario 3: Manual vs device conflict
            if scenario == "manual_device_conflict" and metric == "systolic_bp" and day == 26:
                device_ts = ts_base
                records.append(
                    _make_reading_record(
                        patient_id, device_ts, metric, val, "device",
                        connectivity, "good", records, notes="Automated cuff", scenario=scenario
                    )
                )
                manual_ts = device_ts + pd.Timedelta(hours=1)
                records.append(
                    _make_reading_record(
                        patient_id, manual_ts, metric, val - 24.0, "manual",
                        connectivity, "good", records, notes="Home manual cuff contradicts device",
                        scenario=scenario
                    )
                )
                continue

            # Periodic health worker visit on day 14 and 28
            if day in (14, 28) and metric == "systolic_bp" and scenario not in ("multi_week_outage", "insufficient_data"):
                hw_ts = ts_base + pd.Timedelta(hours=3)
                records.append(
                    _make_reading_record(
                        patient_id, hw_ts, metric, val + float(rng.normal(0, 1.5)),
                        "health_worker", "online", "good", records,
                        notes="Community health worker check", scenario=scenario
                    )
                )

            records.append(
                _make_reading_record(
                    patient_id, ts_base, metric, val, source,
                    connectivity, q, records, notes=notes, scenario=scenario
                )
            )

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values(["metric", "timestamp"]).reset_index(drop=True)
    return df


def generate_review3_cohort(seed: int = 2026) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate the complete 200-profile Review 3 cohort.

    Returns:
        (readings_df, labels_df)
    """
    frames = []
    labels = []
    idx = 1
    now = pd.Timestamp.now(tz="UTC")

    for scenario, reliable, alert, count in REVIEW3_COHORT_PLAN:
        for _ in range(count):
            pid = f"R3-{idx:03d}"
            df = generate_review3_patient(pid, scenario, seed=seed + idx, now=now)
            frames.append(df)
            labels.append({
                "patient_id": pid,
                "scenario": scenario,
                "ground_truth_reliable": bool(reliable),
                "ground_truth_alert": bool(alert),
            })
            idx += 1

    combined_readings = pd.concat(frames, ignore_index=True)
    label_df = pd.DataFrame(labels)
    return combined_readings, label_df


def save_review3_cohort(output_dir: str | Path, seed: int = 2026) -> tuple[Path, Path]:
    """Generate and save Review 3 cohort datasets to CSV."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    readings, labels = generate_review3_cohort(seed=seed)
    r_path = out / "review3_readings.csv"
    l_path = out / "review3_labels.csv"
    readings.to_csv(r_path, index=False)
    labels.to_csv(l_path, index=False)
    return r_path, l_path


def get_cohort_summary(readings: pd.DataFrame, labels: pd.DataFrame) -> dict:
    """Summarize cohort characteristics for documentation and evaluation."""
    n_profiles = len(labels)
    n_readings = len(readings)
    scenarios = labels["scenario"].value_counts().to_dict()
    conn_counts = readings["connectivity_status"].value_counts().to_dict()
    quality_counts = readings["quality_label"].value_counts().to_dict()
    source_counts = readings["source"].value_counts().to_dict()

    reliable_count = int(labels["ground_truth_reliable"].sum())
    alert_count = int(labels["ground_truth_alert"].sum())

    return {
        "n_profiles": n_profiles,
        "n_readings": n_readings,
        "scenarios": scenarios,
        "reliable_profiles": reliable_count,
        "unreliable_profiles": n_profiles - reliable_count,
        "true_alert_profiles": alert_count,
        "connectivity_distribution": conn_counts,
        "quality_distribution": quality_counts,
        "source_distribution": source_counts,
        "metrics_covered": sorted(readings["metric"].unique().tolist()),
    }
