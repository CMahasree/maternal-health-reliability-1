"""Simulated maternal health device readings with realistic gaps and failures."""

from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from maternal_reliability.data.schema import (
    CONNECTIVITY,
    EXPECTED_INTERVAL_HOURS,
    METRICS,
    QUALITY_LABELS,
    SOURCES,
)


def _base_value(metric: str, day: int, patient_seed: int) -> float:
    """Generate baseline physiological values with slight patient variation."""
    rng = np.random.default_rng(patient_seed + day)
    bases = {
        "systolic_bp": 118 + patient_seed % 10,
        "diastolic_bp": 72 + patient_seed % 5,
        "heart_rate": 78 + patient_seed % 8,
        "weight_kg": 68.0 + (day * 0.08) + (patient_seed % 3) * 0.5,
        "fetal_movement": 8 + patient_seed % 4,
    }
    noise = {
        "systolic_bp": rng.normal(0, 3),
        "diastolic_bp": rng.normal(0, 2),
        "heart_rate": rng.normal(0, 4),
        "weight_kg": rng.normal(0, 0.2),
        "fetal_movement": rng.integers(-2, 3),
    }
    return float(bases[metric] + noise[metric])


def _apply_scenario_effects(
    metric: str,
    day: int,
    value: float,
    scenario: str,
    patient_idx: int,
) -> float:
    """Apply scenario-specific perturbations to simulate edge cases."""
    if scenario == "multi_week_outage":
        return value  # gaps handled separately
    if scenario == "manual_device_conflict" and metric == "systolic_bp" and day >= 25:
        return value  # conflict injected at manual entry layer
    if scenario == "sensor_malfunction" and metric in ("systolic_bp", "heart_rate") and day >= 20:
        return value + 35 if metric == "systolic_bp" else value + 40
    if scenario == "concerning_trend" and metric == "systolic_bp" and day >= 10:
        return value + (day - 10) * 1.8
    if scenario == "stable_normal":
        return value
    return value


def generate_patient_readings(
    patient_id: str,
    scenario: str,
    start_date: str | None = None,
    days: int = 42,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate readings for one patient under a given scenario.

    Scenarios:
    - stable_normal: regular device readings, good quality
    - multi_week_outage: 18-day connectivity loss mid-series
    - manual_device_conflict: manual entry contradicts last device BP
    - sensor_malfunction: sudden erroneous readings after day 20
    - concerning_trend: gradual BP rise (ground truth alert)
    - irregular_timing: measurement frequency changes mid-series
    """
    rng = np.random.default_rng(seed)
    patient_seed = int(patient_id.replace("P", "")) if patient_id[1:].isdigit() else seed
    if start_date is None:
        start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
    else:
        start = pd.Timestamp(start_date, tz="UTC")
    records: list[dict] = []

    outage_start, outage_end = 14, 32
    freq_change_day = 21

    for day in range(days):
        skip_day = False
        connectivity = "online"
        quality = "good"

        if scenario == "multi_week_outage" and outage_start <= day < outage_end:
            skip_day = True
            connectivity = "offline"

        if scenario == "irregular_timing" and day >= freq_change_day:
            # Measure every 3 days instead of daily
            if day % 3 != 0:
                continue

        if skip_day:
            continue

        # Intermittent connectivity noise
        if rng.random() < 0.08:
            connectivity = "intermittent"
        if connectivity == "intermittent" and rng.random() < 0.3:
            quality = "suspect"

        ts_base = start + pd.Timedelta(days=day, hours=int(rng.integers(6, 20)))

        for metric in METRICS:
            # Weight doesn't need daily
            if metric == "weight_kg" and day % 7 != 0:
                continue
            if metric == "fetal_movement" and day % 2 != 0:
                continue

            value = _base_value(metric, day, patient_seed)
            value = _apply_scenario_effects(metric, day, value, scenario, patient_seed)

            if scenario == "sensor_malfunction" and day >= 20 and metric in ("systolic_bp", "heart_rate"):
                quality = "good"  # undetected malfunction — device still reports

            source = "device"
            notes = ""

            # Timestamp irregularity: +/- 6 hours jitter, occasional duplicate hour
            jitter_hours = float(rng.integers(-6, 7))
            if scenario == "irregular_timing" and day >= freq_change_day:
                jitter_hours += float(rng.integers(-12, 13))

            # Manual entry on day 26 for conflict scenario (after device reading)
            if scenario == "manual_device_conflict" and metric == "systolic_bp" and day == 26:
                device_ts = ts_base + pd.Timedelta(hours=jitter_hours)
                device_value = value
                records.append(
                    _make_record(
                        patient_id, device_ts, metric, device_value,
                        "device", connectivity, "good", records,
                    )
                )
                manual_ts = device_ts + pd.Timedelta(hours=1)
                records.append(
                    _make_record(
                        patient_id, manual_ts, metric, device_value - 22,
                        "manual", connectivity, "good", records,
                        notes="Home cuff reading contradicts device",
                    )
                )
                continue  # skip default append for this metric/day

            # Occasional health worker visits
            if day % 14 == 0 and metric == "systolic_bp":
                hw_ts = ts_base + pd.Timedelta(hours=4)
                records.append(
                    _make_record(
                        patient_id, hw_ts, metric, value + rng.normal(0, 2),
                        "health_worker", "online", "good", records,
                    )
                )

            ts = ts_base + pd.Timedelta(hours=jitter_hours)
            records.append(
                _make_record(
                    patient_id, ts, metric, value, source, connectivity, quality, records, notes,
                )
            )

    df = pd.DataFrame(records)
    return df.sort_values(["metric", "timestamp"]).reset_index(drop=True)


def _make_record(
    patient_id: str,
    timestamp: pd.Timestamp,
    metric: str,
    value: float,
    source: str,
    connectivity: str,
    quality: str,
    prior_records: list[dict],
    notes: str = "",
) -> dict:
    """Build a single reading record with gap calculation."""
    device_id = f"DEV-{patient_id}-001"
    gap_hours = np.nan
    is_gap = False

    same_metric = [r for r in prior_records if r["metric"] == metric and r["patient_id"] == patient_id]
    if same_metric:
        last_ts = same_metric[-1]["timestamp"]
        gap_hours = (timestamp - last_ts).total_seconds() / 3600.0
        expected = EXPECTED_INTERVAL_HOURS.get(metric, 24.0)
        is_gap = gap_hours > expected * 2

    return {
        "reading_id": str(uuid.uuid4())[:8],
        "patient_id": patient_id,
        "timestamp": timestamp,
        "metric": metric,
        "value": round(float(value), 2),
        "source": source,
        "device_id": device_id,
        "connectivity_status": connectivity,
        "quality_label": quality,
        "gap_before_hours": gap_hours if not np.isnan(gap_hours) else 0.0,
        "is_gap": is_gap,
        "notes": notes,
    }


def generate_simulated_dataset(seed: int = 42) -> pd.DataFrame:
    """Generate full multi-patient simulated dataset with ground-truth labels."""
    scenarios = [
        ("P001", "stable_normal", True, False),       # reliable, no alert
        ("P002", "concerning_trend", True, True),     # reliable, true alert
        ("P003", "multi_week_outage", False, False),  # unreliable, no real trend
        ("P004", "manual_device_conflict", False, False),
        ("P005", "sensor_malfunction", False, False),  # unreliable; raw trend is artifact
        ("P006", "irregular_timing", False, False),
        ("P007", "stable_normal", True, False),
        ("P008", "concerning_trend", True, True),
    ]

    frames = []
    labels = []
    for i, (pid, scenario, reliable, alert) in enumerate(scenarios):
        df = generate_patient_readings(pid, scenario, seed=seed + i)
        df["scenario"] = scenario
        frames.append(df)
        labels.append({
            "patient_id": pid,
            "scenario": scenario,
            "ground_truth_reliable": reliable,
            "ground_truth_alert": alert,
        })

    combined = pd.concat(frames, ignore_index=True)
    label_df = pd.DataFrame(labels)
    return combined, label_df


def save_dataset(output_dir: str | Path, seed: int = 42) -> tuple[Path, Path]:
    """Generate and persist simulated dataset to CSV."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    readings, labels = generate_simulated_dataset(seed=seed)
    readings_path = output_dir / "simulated_readings.csv"
    labels_path = output_dir / "ground_truth_labels.csv"

    readings.to_csv(readings_path, index=False)
    labels.to_csv(labels_path, index=False)
    return readings_path, labels_path
