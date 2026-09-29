"""Uncertainty quantification for trend assessments."""

from __future__ import annotations

from dataclasses import dataclass

from maternal_reliability.pipeline.reliability_scorer import ReliabilityScore
from maternal_reliability.pipeline.trend_detection import TrendResult


@dataclass
class UncertaintyEstimate:
    """Combined uncertainty from data reliability and trend statistics."""

    patient_id: str
    metric: str
    confidence: float  # 0-100, actionable confidence
    reliability_contribution: float
    trend_contribution: float
    interval_description: str
    factors: list[str]


def quantify_uncertainty(reliability: ReliabilityScore, trend: TrendResult) -> UncertaintyEstimate:
    """
    Quantify uncertainty by combining reliability score and trend fit quality.

    High reliability + significant trend = higher confidence.
    Low reliability or weak trend = lower confidence with explicit factors.
    """
    rel_factor = reliability.score / 100.0
    trend_factor = 1.0

    if trend.n_points < 5:
        trend_factor *= 0.5
    if trend.p_value >= 0.05:
        trend_factor *= 0.6
    elif trend.p_value >= 0.01:
        trend_factor *= 0.85

    confidence = 100.0 * rel_factor * trend_factor
    confidence = min(confidence, reliability.score)

    factors = list(reliability.rationale)
    if trend.n_points < 5:
        factors.append(f"Only {trend.n_points} points in trend window")
    if trend.p_value >= 0.05:
        factors.append(f"Trend not statistically significant (p={trend.p_value})")
    if trend.direction == "insufficient_data":
        factors.append("Insufficient data for trend analysis")

    if confidence >= 75:
        interval = "High confidence — trend estimate likely reflects true change"
    elif confidence >= 50:
        interval = "Moderate confidence — verify with additional readings before action"
    else:
        interval = "Low confidence — do not act on trend alone"

    return UncertaintyEstimate(
        patient_id=reliability.patient_id,
        metric=reliability.metric,
        confidence=round(confidence, 1),
        reliability_contribution=round(reliability.score, 1),
        trend_contribution=round(trend_factor * 100, 1),
        interval_description=interval,
        factors=factors,
    )
