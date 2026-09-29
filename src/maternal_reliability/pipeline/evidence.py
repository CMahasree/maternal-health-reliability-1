"""Evidence chain documentation for audit trail."""

from __future__ import annotations

from dataclasses import dataclass, field

from maternal_reliability.pipeline.harm_assessment import HarmAssessment
from maternal_reliability.pipeline.quality_check import QualityReport
from maternal_reliability.pipeline.reliability_scorer import ReliabilityScore
from maternal_reliability.pipeline.trend_detection import TrendResult
from maternal_reliability.pipeline.uncertainty import UncertaintyEstimate


@dataclass
class EvidenceChain:
    """Complete evidence trail linking data points to decision."""

    patient_id: str
    metric: str
    summary: str
    data_points: list[dict] = field(default_factory=list)
    quality_factors: list[str] = field(default_factory=list)
    score_breakdown: dict = field(default_factory=dict)
    trend_summary: str = ""
    uncertainty_summary: str = ""
    harm_summary: str = ""


def build_evidence_chain(
    quality: QualityReport,
    reliability: ReliabilityScore,
    trend: TrendResult,
    uncertainty: UncertaintyEstimate,
    harm: HarmAssessment,
) -> EvidenceChain:
    """Build auditable evidence chain for clinical review."""
    data_points = [
        {
            "reading_ids": trend.evidence_points[:10],
            "total_in_window": trend.n_points,
            "quality_reading_ids": quality.contributing_readings[:10],
        }
    ]

    trend_summary = (
        f"{trend.direction} trend (slope={trend.slope_per_day}/day, p={trend.p_value}), "
        f"concerning={trend.concerning}, n={trend.n_points}"
    )
    uncertainty_summary = (
        f"Confidence={uncertainty.confidence}%, {uncertainty.interval_description}"
    )
    harm_summary = (
        f"Total harm if acted upon={harm.total_harm_score}; {len(harm.harm_items)} risk factor(s)"
    )

    summary = (
        f"Reliability {reliability.score}/100 ({reliability.label.value}); "
        f"{trend_summary}; {uncertainty_summary}"
    )

    quality_factors = quality.warnings + reliability.rationale

    return EvidenceChain(
        patient_id=quality.patient_id,
        metric=quality.metric,
        summary=summary,
        data_points=data_points,
        quality_factors=quality_factors,
        score_breakdown=reliability.components,
        trend_summary=trend_summary,
        uncertainty_summary=uncertainty_summary,
        harm_summary=harm_summary,
    )
