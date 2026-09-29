"""End-to-end pipeline orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from maternal_reliability.config import OPERATIONAL_LIMITS
from maternal_reliability.data.schema import validate_dataframe
from maternal_reliability.pipeline.decision import ClinicalDecision, make_decision
from maternal_reliability.pipeline.evidence import EvidenceChain, build_evidence_chain
from maternal_reliability.pipeline.harm_assessment import HarmAssessment, assess_harm
from maternal_reliability.pipeline.quality_check import QualityReport, check_quality
from maternal_reliability.pipeline.reliability_scorer import ReliabilityScore, score_reliability
from maternal_reliability.pipeline.trend_detection import TrendResult, detect_trend
from maternal_reliability.pipeline.uncertainty import UncertaintyEstimate, quantify_uncertainty


@dataclass
class AssessmentResult:
    """Complete pipeline output for one patient-metric."""

    patient_id: str
    metric: str
    quality: QualityReport
    reliability: ReliabilityScore
    trend: TrendResult
    uncertainty: UncertaintyEstimate
    harm: HarmAssessment
    evidence: EvidenceChain
    decision: ClinicalDecision


@dataclass
class PipelineResult:
    """Batch pipeline output."""

    assessments: list[AssessmentResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    truncated: bool = False


def assess_patient(
    df: pd.DataFrame,
    patient_id: str,
    metric: str = "systolic_bp",
) -> AssessmentResult:
    """Run full pipeline for a single patient-metric."""
    quality = check_quality(df, patient_id, metric)
    reliability = score_reliability(quality)
    trend = detect_trend(df, patient_id, metric)
    uncertainty = quantify_uncertainty(reliability, trend)
    harm = assess_harm(reliability, trend, uncertainty)
    evidence = build_evidence_chain(quality, reliability, trend, uncertainty, harm)
    decision = make_decision(reliability, trend, uncertainty, harm, evidence)

    return AssessmentResult(
        patient_id=patient_id,
        metric=metric,
        quality=quality,
        reliability=reliability,
        trend=trend,
        uncertainty=uncertainty,
        harm=harm,
        evidence=evidence,
        decision=decision,
    )


def run_pipeline(
    df: pd.DataFrame,
    metrics: list[str] | None = None,
    patient_ids: list[str] | None = None,
) -> PipelineResult:
    """
    Run pipeline for all patients and metrics with capacity limits.

    Respects max_pending_assessments operational limit.
    """
    df, warnings = validate_dataframe(df)
    result = PipelineResult(warnings=warnings)

    if patient_ids is None:
        patient_ids = df["patient_id"].unique().tolist()
    if metrics is None:
        metrics = ["systolic_bp"]

    tasks = [(p, m) for p in patient_ids for m in metrics]
    max_n = OPERATIONAL_LIMITS.max_pending_assessments
    if len(tasks) > max_n:
        tasks = tasks[:max_n]
        result.truncated = True
        result.warnings.append(
            f"Truncated to {max_n} assessments (capacity limit)"
        )

    for pid, metric in tasks:
        try:
            assessment = assess_patient(df, pid, metric)
            result.assessments.append(assessment)
        except Exception as exc:
            result.warnings.append(f"Failed {pid}/{metric}: {exc}")

    return result


def assessment_to_dict(a: AssessmentResult) -> dict:
    """Serialize assessment for dashboard and reports."""
    return {
        "patient_id": a.patient_id,
        "metric": a.metric,
        "reliability_score": a.reliability.score,
        "reliability_label": a.reliability.label.value,
        "components": a.reliability.components,
        "rationale": a.reliability.rationale,
        "trend_direction": a.trend.direction,
        "trend_concerning": a.trend.concerning,
        "trend_slope": a.trend.slope_per_day,
        "trend_p_value": a.trend.p_value,
        "confidence": a.uncertainty.confidence,
        "harm_score": a.harm.total_harm_score,
        "harm_items": a.harm.harm_items,
        "decision": a.decision.outcome.value,
        "alert": a.decision.alert,
        "message": a.decision.message,
        "fallback_actions": a.decision.fallback_actions,
        "evidence_summary": a.evidence.summary,
        "evidence_points": a.trend.evidence_points,
        "quality_warnings": a.quality.warnings,
    }
