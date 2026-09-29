"""Baseline reference scorer for comparison."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from maternal_reliability.config import BASELINE_MISSING_DATA_THRESHOLD
from maternal_reliability.pipeline.quality_check import check_quality
from maternal_reliability.pipeline.trend_detection import TrendResult, detect_trend


@dataclass
class BaselineResult:
    """Baseline scorer output."""

    patient_id: str
    metric: str
    alert: bool
    missing_rate: float
    trend_concerning: bool
    reason: str


def baseline_score(
    df: pd.DataFrame,
    patient_id: str,
    metric: str = "systolic_bp",
) -> BaselineResult:
    """
    Simple baseline: flag concerning trend if missing data <= 20%.

    This naive approach ignores source conflicts, connectivity, and quality flags.
    """
    quality = check_quality(df, patient_id, metric)
    # Baseline uses all readings including bad-quality (naive approach)
    trend = detect_trend(df, patient_id, metric, exclude_bad_quality=False)

    reliable_enough = quality.missing_rate <= BASELINE_MISSING_DATA_THRESHOLD
    alert = reliable_enough and trend.concerning

    if not reliable_enough and trend.concerning:
        reason = f"Trend detected but missing rate {quality.missing_rate:.0%} > 20% threshold"
    elif alert:
        reason = "Concerning trend with acceptable missing data (baseline)"
    elif trend.concerning:
        reason = "Concerning trend suppressed due to missing data"
    else:
        reason = "No concerning trend"

    return BaselineResult(
        patient_id=patient_id,
        metric=metric,
        alert=alert,
        missing_rate=quality.missing_rate,
        trend_concerning=trend.concerning,
        reason=reason,
    )


def run_baseline_batch(
    df: pd.DataFrame,
    patient_ids: list[str] | None = None,
    metric: str = "systolic_bp",
) -> list[BaselineResult]:
    """Run baseline scorer on all patients."""
    if patient_ids is None:
        patient_ids = df["patient_id"].unique().tolist()
    return [baseline_score(df, pid, metric) for pid in patient_ids]
