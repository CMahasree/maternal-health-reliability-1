"""Clinical decision with safe fallback."""

from __future__ import annotations

from dataclasses import dataclass, field

from maternal_reliability.config import THRESHOLDS, DecisionOutcome
from maternal_reliability.pipeline.evidence import EvidenceChain
from maternal_reliability.pipeline.harm_assessment import HarmAssessment
from maternal_reliability.pipeline.reliability_scorer import ReliabilityScore
from maternal_reliability.pipeline.trend_detection import TrendResult
from maternal_reliability.pipeline.uncertainty import UncertaintyEstimate


@dataclass
class ClinicalDecision:
    """Final decision output with safe fallback guidance."""

    patient_id: str
    metric: str
    outcome: DecisionOutcome
    alert: bool
    message: str
    fallback_actions: list[str] = field(default_factory=list)
    recheck_in_hours: int = 24
    evidence_summary: str = ""


def make_decision(
    reliability: ReliabilityScore,
    trend: TrendResult,
    uncertainty: UncertaintyEstimate,
    harm: HarmAssessment,
    evidence: EvidenceChain,
) -> ClinicalDecision:
    """
    Determine clinical action with safe fallback when reliability is insufficient.

    Decision logic:
    - ACTIONABLE: reliability >= 70, concerning trend, confidence >= 60
    - CAUTION: reliability 50-69 or confidence 40-59 with concerning trend
    - SAFE_FALLBACK: reliability < 50 or severe data quality issues
    - NOT_ACTIONABLE: no concerning trend or insufficient data
    """
    t = THRESHOLDS
    fallback_actions: list[str] = []

    if reliability.score < t.caution_min:
        outcome = DecisionOutcome.SAFE_FALLBACK
        alert = False
        message = (
            "Data reliability too low for clinical action. "
            "Trend analysis suspended until data quality improves."
        )
        fallback_actions = [
            "Contact patient to verify device connectivity",
            "Request health worker home visit for manual vitals",
            "Collect 3 consecutive daily readings before re-assessment",
            "Do NOT schedule clinic visit based on current trend",
        ]
    elif trend.concerning and reliability.score >= t.actionable_min and uncertainty.confidence >= 60:
        outcome = DecisionOutcome.ACTIONABLE
        alert = True
        message = (
            f"Concerning {trend.direction} trend in {reliability.metric} "
            f"with adequate reliability ({reliability.score}/100). Recommend clinical follow-up."
        )
        fallback_actions = ["Schedule clinic review within 48 hours"]
    elif trend.concerning and reliability.score >= t.caution_min:
        outcome = DecisionOutcome.CAUTION
        alert = False
        message = (
            "Possible concerning trend detected but confidence is insufficient. "
            "Verify before clinical action."
        )
        fallback_actions = [
            "Obtain confirmatory reading within 24 hours",
            "Compare manual and device readings",
            "Escalate to clinician if second reading confirms trend",
        ]
    else:
        outcome = DecisionOutcome.NOT_ACTIONABLE
        alert = False
        message = "No actionable concerning trend at current data quality."
        fallback_actions = ["Continue routine monitoring per care plan"]

    if harm.total_harm_score > 15 and outcome != DecisionOutcome.ACTIONABLE:
        fallback_actions.insert(0, harm.recommendation)

    return ClinicalDecision(
        patient_id=reliability.patient_id,
        metric=reliability.metric,
        outcome=outcome,
        alert=alert,
        message=message,
        fallback_actions=fallback_actions,
        recheck_in_hours=24 if outcome == DecisionOutcome.SAFE_FALLBACK else 48,
        evidence_summary=evidence.summary,
    )
