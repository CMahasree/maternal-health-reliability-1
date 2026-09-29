"""Review 2 expanded cohort — does not replace the Review 1 8-patient generator."""

from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from maternal_reliability.data.schema import EXPECTED_INTERVAL_HOURS, REVIEW2_METRICS

# 180 profiles: original 160 plus reduced-FM and fever slices for new biometrics.
COHORT_PLAN = (
    ("stable_normal", "low", 40),
    ("low_risk_borderline", "low", 20),
    ("medium_hypertension", "medium", 25),
    ("high_preeclampsia_range", "high", 25),
    ("gestational_diabetes", "medium", 15),
    ("missing_data", "low", 15),  # intended physiology is normal; data is incomplete
    ("noisy_sensor", "low", 12),  # true low; artifacts look high
    ("manual_conflict", "low", 8),
    ("reduced_fetal_movement", "medium", 12),
    ("maternal_fever", "medium", 8),
)

COHORT_N = sum(n for _, _, n in COHORT_PLAN)

SCENARIO_CATEGORY = {
    "stable_normal": "normal",
    "low_risk_borderline": "low_risk",
    "medium_hypertension": "medium_risk",
    "high_preeclampsia_range": "high_risk",
    "gestational_diabetes": "medium_risk",
    "missing_data": "missing_data",
    "noisy_sensor": "noisy_data",
    "manual_conflict": "corner_case",
    "reduced_fetal_movement": "medium_risk",
    "maternal_fever": "medium_risk",
}


def _record(
    patient_id: str,
    timestamp: pd.Timestamp,
    metric: str,
    value: float,
    source: str,
    connectivity: str,
    quality: str,
    prior: list[dict],
    notes: str = "",
) -> dict:
    gap_hours = 0.0
    is_gap = False
    same = [r for r in prior if r["metric"] == metric]
    if same:
        gap_hours = (timestamp - same[-1]["timestamp"]).total_seconds() / 3600.0
        expected = EXPECTED_INTERVAL_HOURS.get(metric, 24.0)
        is_gap = gap_hours > expected * 2
    return {
        "reading_id": str(uuid.uuid4())[:8],
        "patient_id": patient_id,
        "timestamp": timestamp,
        "metric": metric,
        "value": round(float(value), 2),
        "source": source,
        "device_id": f"DEV-{patient_id}-R2",
        "connectivity_status": connectivity,
        "quality_label": quality,
        "gap_before_hours": gap_hours,
        "is_gap": is_gap,
        "notes": notes,
    }


def _physiology(scenario: str, day: int, rng: np.random.Generator) -> dict[str, float]:
    """Intended (ground-truth) physiology before device artifacts."""
    sbp, dbp, hr, wt, glu, hrv = 118, 74, 80, 68.0 + day * 0.05, 88, 32.0
    fm, temp, spo2 = 12.0, 36.7, 98.0
    if scenario == "low_risk_borderline":
        sbp, dbp, glu = 132, 84, 93
    elif scenario == "medium_hypertension":
        sbp, dbp = 148, 96
        if day >= 8:
            sbp += (day - 8) * 0.4
            dbp += (day - 8) * 0.25
    elif scenario == "high_preeclampsia_range":
        sbp, dbp, hrv = 168, 114, 13.0
        wt = 68.0 + day * 0.18
        fm = 9.0
        if day >= 5:
            sbp += (day - 5) * 0.6
    elif scenario == "gestational_diabetes":
        glu = 108 if day < 20 else 118  # IADPSG-elevated fasting proxy, below 126
        sbp, dbp = 126, 80
    elif scenario == "missing_data":
        sbp, dbp = 120, 76
    elif scenario == "noisy_sensor":
        sbp, dbp, glu, hr = 118, 74, 86, 78
    elif scenario == "manual_conflict":
        sbp, dbp = 122, 78
    elif scenario == "reduced_fetal_movement":
        fm = 4.0
        sbp, dbp = 124, 78
    elif scenario == "maternal_fever":
        temp, hr, spo2 = 38.4, 108, 96.0
        sbp, dbp = 122, 78

    return {
        "systolic_bp": sbp + float(rng.normal(0, 2.5)),
        "diastolic_bp": dbp + float(rng.normal(0, 1.8)),
        "heart_rate": hr + float(rng.normal(0, 3.0)),
        "weight_kg": wt + float(rng.normal(0, 0.15)),
        "blood_glucose_mgdl": glu + float(rng.normal(0, 4.0)),
        "hrv_rmssd_ms": max(8.0, hrv + float(rng.normal(0, 2.0))),
        "fetal_movement": max(0.0, fm + float(rng.normal(0, 0.8))),
        "temperature_c": temp + float(rng.normal(0, 0.12)),
        "spo2_pct": min(100.0, max(80.0, spo2 + float(rng.normal(0, 0.6)))),
    }


def generate_review2_patient(
    patient_id: str,
    scenario: str,
    seed: int,
    days: int = 28,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-01-01", tz="UTC")
    records: list[dict] = []
    outage_start, outage_end = 8, 22

    for day in range(days):
        connectivity = "online"
        quality = "good"
        skip = False

        if scenario == "missing_data" and outage_start <= day < outage_end:
            skip = True
            connectivity = "offline"
        if scenario == "missing_data" and rng.random() < 0.25:
            skip = True

        if rng.random() < 0.12:
            connectivity = "intermittent"
        elif rng.random() < 0.10:
            # Stored local cache — not a skipped gap (missing_data still skips outage days).
            connectivity = "offline"
        if connectivity == "intermittent" and rng.random() < 0.35:
            quality = "suspect"

        if skip:
            continue

        ts_base = start + pd.Timedelta(days=day, hours=int(rng.integers(6, 18)))
        phys = _physiology(scenario, day, rng)

        for metric in REVIEW2_METRICS:
            if metric == "weight_kg" and day % 7 != 0:
                continue

            value = phys[metric]
            q = quality
            source = "device"
            notes = ""

            if scenario == "noisy_sensor" and day >= 12 and metric in (
                "systolic_bp",
                "diastolic_bp",
                "heart_rate",
            ):
                value += 42 if "bp" in metric else 38
                q = "good"
                notes = "undetected spike"

            if scenario == "manual_conflict" and metric == "systolic_bp" and day == 18:
                device_ts = ts_base
                records.append(
                    _record(patient_id, device_ts, metric, value, "device", connectivity, "good", records)
                )
                records.append(
                    _record(
                        patient_id,
                        device_ts + pd.Timedelta(hours=1),
                        metric,
                        value - 24,
                        "manual",
                        connectivity,
                        "good",
                        records,
                        notes="Home cuff contradicts device",
                    )
                )
                continue

            jitter = float(rng.integers(-5, 6))
            ts = ts_base + pd.Timedelta(hours=jitter)
            records.append(_record(patient_id, ts, metric, value, source, connectivity, q, records, notes))

    return pd.DataFrame(records)


def generate_review2_cohort(seed: int = 2026) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    labels = []
    idx = 1
    for scenario, true_risk, n in COHORT_PLAN:
        for k in range(n):
            pid = f"R2-{idx:03d}"
            df = generate_review2_patient(pid, scenario, seed=seed + idx)
            df["scenario"] = scenario
            frames.append(df)
            labels.append(
                {
                    "patient_id": pid,
                    "scenario": scenario,
                    "category": SCENARIO_CATEGORY[scenario],
                    "ground_truth_risk": true_risk,
                    "corner_case": scenario in ("missing_data", "noisy_sensor", "manual_conflict"),
                }
            )
            idx += 1
    readings = pd.concat(frames, ignore_index=True)
    return readings, pd.DataFrame(labels)


def save_review2_cohort(output_dir: str | Path, seed: int = 2026) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    readings, labels = generate_review2_cohort(seed=seed)
    r_path = output_dir / "review2_readings.csv"
    l_path = output_dir / "review2_labels.csv"
    readings.to_csv(r_path, index=False)
    labels.to_csv(l_path, index=False)
    return r_path, l_path
