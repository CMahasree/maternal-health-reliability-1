"""Trend detection for maternal health metrics."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from maternal_reliability.config import TREND_CONFIG


@dataclass
class TrendResult:
    """Detected trend with statistical details."""

    patient_id: str
    metric: str
    has_trend: bool
    direction: str  # rising | falling | stable | insufficient_data
    slope_per_day: float
    p_value: float
    concerning: bool
    n_points: int
    window_start: pd.Timestamp | None
    window_end: pd.Timestamp | None
    evidence_points: list[dict] = field(default_factory=list)


def detect_trend(
    df: pd.DataFrame,
    patient_id: str,
    metric: str,
    window_days: int | None = None,
    exclude_bad_quality: bool = True,
) -> TrendResult:
    """
    Detect linear trend in recent readings using Theil-Sen robust slope.

    Flags concerning trends based on clinical slope thresholds.
    """
    cfg = TREND_CONFIG
    window_days = window_days or cfg.window_days

    subset = df[(df["patient_id"] == patient_id) & (df["metric"] == metric)].copy()
    if subset.empty:
        return TrendResult(
            patient_id=patient_id,
            metric=metric,
            has_trend=False,
            direction="insufficient_data",
            slope_per_day=0.0,
            p_value=1.0,
            concerning=False,
            n_points=0,
            window_start=None,
            window_end=None,
        )

    # 1. Isolate recent time window (default 14 days) relative to the most recent measurement
    subset = subset.sort_values("timestamp")
    end = subset["timestamp"].max()
    start = end - pd.Timedelta(days=window_days)
    window = subset[subset["timestamp"] >= start]

    # 2. Prioritize clean device readings: exclude bad-quality records and prefer automated device data
    if exclude_bad_quality and "quality_label" in window.columns:
        window = window[window["quality_label"] != "bad"]
    if "source" in window.columns:
        device = window[window["source"] == "device"]
        if len(device) >= cfg.min_points:
            window = device

    # 3. Enforce statistical power threshold: minimum 5 valid observations required
    n = len(window)
    if n < cfg.min_points:
        return TrendResult(
            patient_id=patient_id,
            metric=metric,
            has_trend=False,
            direction="insufficient_data",
            slope_per_day=0.0,
            p_value=1.0,
            concerning=False,
            n_points=n,
            window_start=start,
            window_end=end,
        )

    # 4. Fit linear regression over time axis converted to fractional days
    t0 = window["timestamp"].min()
    x = (window["timestamp"] - t0).dt.total_seconds() / 86400.0
    y = window["value"].values

    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    # A statistically meaningful trend requires significance (p < 0.05) and moderate correlation (|r| > 0.3)
    has_trend = p_value < cfg.significance_p_value and abs(r_value) > 0.3

    # Direction categorization based on daily rate of change
    if slope > 0.05:
        direction = "rising"
    elif slope < -0.05:
        direction = "falling"
    else:
        direction = "stable"

    # 5. Evaluate clinical concern against guideline-derived daily slope thresholds
    concerning = False
    if metric == "systolic_bp" and slope >= cfg.concerning_slope_bp_per_day and has_trend:
        concerning = True
    elif metric == "diastolic_bp" and slope >= cfg.concerning_slope_dbp_per_day and has_trend:
        concerning = True
    elif metric == "heart_rate" and slope >= cfg.concerning_slope_hr_per_day and has_trend:
        concerning = True
    elif metric == "blood_glucose_mgdl" and slope >= cfg.concerning_slope_glucose_per_day and has_trend:
        concerning = True
    elif metric == "weight_kg" and slope >= cfg.concerning_slope_weight_kg_per_day and has_trend:
        concerning = True

    evidence = [
        {
            "reading_id": str(row.get("reading_id", "")),
            "timestamp": str(row["timestamp"]),
            "value": float(row["value"]),
            "source": str(row.get("source", "")),
        }
        for _, row in window.iterrows()
    ]

    return TrendResult(
        patient_id=patient_id,
        metric=metric,
        has_trend=has_trend,
        direction=direction,
        slope_per_day=round(float(slope), 3),
        p_value=round(float(p_value), 4),
        concerning=concerning,
        n_points=n,
        window_start=start,
        window_end=end,
        evidence_points=evidence,
    )
