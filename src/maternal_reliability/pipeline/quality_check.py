"""Data quality checks for maternal health readings."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from maternal_reliability.config import OPERATIONAL_LIMITS
from maternal_reliability.data.schema import EXPECTED_INTERVAL_HOURS, validate_dataframe


@dataclass
class QualityReport:
    """Quality check results for a patient-metric series."""

    patient_id: str
    metric: str
    n_readings: int
    n_gaps: int
    missing_rate: float
    irregularity_score: float  # 0=regular, 1=highly irregular
    bad_quality_rate: float
    offline_rate: float
    source_conflict: bool
    conflict_details: str
    stale: bool
    sensor_anomaly: bool
    anomaly_details: str
    warnings: list[str] = field(default_factory=list)
    contributing_readings: list[str] = field(default_factory=list)


def check_quality(df: pd.DataFrame, patient_id: str, metric: str) -> QualityReport:
    """
    Run quality checks on a patient's metric time series.

    Handles missing data, malformed timestamps (via validate_dataframe),
    and device failure indicators.
    """
    warnings: list[str] = []
    subset = df[(df["patient_id"] == patient_id) & (df["metric"] == metric)].copy()

    if subset.empty:
        return QualityReport(
            patient_id=patient_id,
            metric=metric,
            n_readings=0,
            n_gaps=0,
            missing_rate=1.0,
            irregularity_score=1.0,
            bad_quality_rate=1.0,
            offline_rate=1.0,
            source_conflict=False,
            conflict_details="No readings available",
            stale=True,
            sensor_anomaly=False,
            anomaly_details="",
            warnings=["No data for patient-metric combination"],
        )

    subset, val_warnings = validate_dataframe(subset)
    warnings.extend(val_warnings)

    n = len(subset)
    n_gaps = int(subset["is_gap"].sum()) if "is_gap" in subset.columns else 0

    if "timestamp" in subset.columns and n >= 2:
        span_days = (subset["timestamp"].max() - subset["timestamp"].min()).days + 1
        expected = EXPECTED_INTERVAL_HOURS.get(metric, 24.0)
        expected_points = max(1, span_days * 24 / expected)
        missing_rate = max(0.0, 1.0 - n / expected_points)
    else:
        missing_rate = 0.0 if n > 0 else 1.0

    # Regularity: coefficient of variation of inter-reading intervals
    if n >= 3:
        intervals = subset["timestamp"].sort_values().diff().dt.total_seconds().dropna() / 3600.0
        if len(intervals) > 0 and intervals.mean() > 0:
            irregularity_score = float(min(1.0, intervals.std() / intervals.mean()))
        else:
            irregularity_score = 0.5
    else:
        irregularity_score = 0.8 if n < 3 else 0.0

    bad_quality_rate = float((subset["quality_label"].isin(["bad", "suspect"])).mean())
    offline_rate = float((subset["connectivity_status"] == "offline").mean())

    # Source conflict: manual vs nearest prior device within 48h with >10% relative difference
    source_conflict = False
    conflict_details = ""
    device = subset[subset["source"] == "device"].sort_values("timestamp")
    manual = subset[subset["source"].isin(["manual", "health_worker"])].sort_values("timestamp")

    if not device.empty and not manual.empty:
        for _, mrow in manual.iterrows():
            prior_device = device[device["timestamp"] < mrow["timestamp"]]
            if prior_device.empty:
                prior_device = device[device["timestamp"] <= mrow["timestamp"]]
            if prior_device.empty:
                continue
            last_device = prior_device.iloc[-1]
            time_diff = abs((mrow["timestamp"] - last_device["timestamp"]).total_seconds()) / 3600.0
            if time_diff <= 48:
                rel_diff = abs(mrow["value"] - last_device["value"]) / max(abs(last_device["value"]), 1)
                if rel_diff > 0.10:
                    source_conflict = True
                    conflict_details = (
                        f"Manual ({mrow['value']}) vs device ({last_device['value']}) "
                        f"within {time_diff:.0f}h ({rel_diff:.0%} difference)"
                    )
                    break

    # Stale data check
    latest = subset["timestamp"].max()
    now = pd.Timestamp.now(tz="UTC")
    stale_hours = (now - latest).total_seconds() / 3600.0
    stale = stale_hours > OPERATIONAL_LIMITS.stale_data_hours

    if stale:
        warnings.append(f"Latest reading is {stale_hours:.0f}h old (stale threshold: {OPERATIONAL_LIMITS.stale_data_hours}h)")

    # Sudden step-change detection (potential sensor malfunction).
    # Uses consecutive-reading jumps, not deviation from historical median, so gradual
    # clinical trends (e.g. rising BP) are not misclassified as sensor failures.
    sensor_anomaly = False
    anomaly_details = ""
    if n >= 5:
        vals = subset.sort_values("timestamp")["value"].values.astype(float)
        rel_jumps = np.abs(np.diff(vals)) / np.maximum(np.abs(vals[:-1]), 1.0)
        max_idx = int(np.argmax(rel_jumps))
        max_jump = float(rel_jumps[max_idx])

        if max_jump > 0.20:
            prior_jumps = rel_jumps[:max_idx] if max_idx > 0 else rel_jumps[1:]
            prior_median = float(np.median(prior_jumps)) if len(prior_jumps) > 0 else 0.0
            is_isolated = prior_median < max_jump * 0.5

            # Flag isolated step-changes anywhere in the series (not only the last reading).
            if is_isolated:
                sensor_anomaly = True
                before_val = vals[max_idx]
                after_val = vals[max_idx + 1]
                anomaly_details = (
                    f"Sudden jump {before_val:.1f} → {after_val:.1f} "
                    f"({max_jump:.0%} change) inconsistent with prior readings"
                )
                warnings.append(anomaly_details)

    contributing = subset["reading_id"].astype(str).tolist() if "reading_id" in subset.columns else []

    return QualityReport(
        patient_id=patient_id,
        metric=metric,
        n_readings=n,
        n_gaps=n_gaps,
        missing_rate=float(np.clip(missing_rate, 0, 1)),
        irregularity_score=float(np.clip(irregularity_score, 0, 1)),
        bad_quality_rate=bad_quality_rate,
        offline_rate=offline_rate,
        source_conflict=source_conflict,
        conflict_details=conflict_details,
        stale=stale,
        sensor_anomaly=sensor_anomaly,
        anomaly_details=anomaly_details,
        warnings=warnings,
        contributing_readings=contributing,
    )
