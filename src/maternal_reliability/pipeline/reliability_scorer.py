"""Reliability scoring from quality metrics."""

from __future__ import annotations

from dataclasses import dataclass, field

from maternal_reliability.config import THRESHOLDS, ReliabilityLabel
from maternal_reliability.pipeline.quality_check import QualityReport


@dataclass
class ReliabilityScore:
    """Composite reliability score with component breakdown."""

    patient_id: str
    metric: str
    score: float
    label: ReliabilityLabel
    components: dict[str, float]
    rationale: list[str] = field(default_factory=list)
    contributing_readings: list[str] = field(default_factory=list)


def _component_completeness(missing_rate: float) -> float:
    return max(0.0, 100.0 * (1.0 - missing_rate))


def _component_regularity(irregularity: float) -> float:
    return max(0.0, 100.0 * (1.0 - irregularity))


def _component_source_agreement(conflict: bool) -> float:
    return 30.0 if conflict else 100.0


def _component_connectivity(offline_rate: float) -> float:
    return max(0.0, 100.0 * (1.0 - offline_rate))


def _component_quality(bad_rate: float) -> float:
    return max(0.0, 100.0 * (1.0 - bad_rate))


def score_reliability(quality: QualityReport) -> ReliabilityScore:
    """
    Compute weighted reliability score (0-100) from quality report.

    Threshold mapping:
    - >= 85: HIGH
    - 70-84: MODERATE (actionable)
    - 50-69: LOW (caution)
    - < 50: UNRELIABLE (safe fallback)
    """
    t = THRESHOLDS
    components = {
        "completeness": _component_completeness(quality.missing_rate),
        "regularity": _component_regularity(quality.irregularity_score),
        "source_agreement": _component_source_agreement(quality.source_conflict),
        "connectivity": _component_connectivity(quality.offline_rate),
        "quality_flags": _component_quality(quality.bad_quality_rate),
    }

    score = (
        t.weight_completeness * components["completeness"]
        + t.weight_regularity * components["regularity"]
        + t.weight_source_agreement * components["source_agreement"]
        + t.weight_connectivity * components["connectivity"]
        + t.weight_quality_flags * components["quality_flags"]
    )

    if quality.n_readings < 3:
        score = min(score, 40.0)

    if quality.stale:
        score = min(score, 55.0)

    rationale = []
    if quality.missing_rate > 0.2:
        rationale.append(f"Missing data rate {quality.missing_rate:.0%} reduces completeness")
    if quality.irregularity_score > 0.5:
        rationale.append(f"Irregular timing (score {quality.irregularity_score:.2f})")
    if quality.source_conflict:
        rationale.append(f"Source conflict: {quality.conflict_details}")
    if quality.offline_rate > 0.3:
        rationale.append(f"High offline rate ({quality.offline_rate:.0%})")
    if quality.bad_quality_rate > 0.2:
        rationale.append(f"Quality flags on {quality.bad_quality_rate:.0%} of readings")

    # Cap score when significant bad-quality or conflict signals present
    if quality.bad_quality_rate > 0.25:
        score = min(score, 55.0)
        if "High proportion of bad/suspect readings" not in rationale:
            rationale.append("High proportion of bad/suspect readings")
    if quality.source_conflict:
        score = min(score, 60.0)
    if quality.missing_rate > 0.35:
        score = min(score, 50.0)
    if quality.sensor_anomaly:
        score = min(score, 55.0)
        rationale.append(f"Sensor anomaly: {quality.anomaly_details}")
    if quality.stale:
        rationale.append("Data is stale relative to recheck interval")
    if quality.n_readings < 3:
        rationale.append(f"Insufficient readings ({quality.n_readings}) for reliable trend")

    if score >= t.high_min:
        label = ReliabilityLabel.HIGH
    elif score >= t.actionable_min:
        label = ReliabilityLabel.MODERATE
    elif score >= t.caution_min:
        label = ReliabilityLabel.LOW
    else:
        label = ReliabilityLabel.UNRELIABLE

    return ReliabilityScore(
        patient_id=quality.patient_id,
        metric=quality.metric,
        score=round(score, 1),
        label=label,
        components=components,
        rationale=rationale,
        contributing_readings=quality.contributing_readings,
    )
