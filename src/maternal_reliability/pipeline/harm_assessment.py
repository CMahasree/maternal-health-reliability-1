"""Harm assessment when acting on unreliable trends."""

from __future__ import annotations

from dataclasses import dataclass, field

from maternal_reliability.config import HARM_COSTS
from maternal_reliability.pipeline.reliability_scorer import ReliabilityScore
from maternal_reliability.pipeline.trend_detection import TrendResult
from maternal_reliability.pipeline.uncertainty import UncertaintyEstimate


@dataclass
class HarmAssessment:
    """Estimated harm if trend were acted upon at current reliability."""

    patient_id: str
    metric: str
    total_harm_score: float
    harm_items: list[dict] = field(default_factory=list)
    recommendation: str = ""


def assess_harm(
    reliability: ReliabilityScore,
    trend: TrendResult,
    uncertainty: UncertaintyEstimate,
) -> HarmAssessment:
    """
    Quantify potential harm from treating an unreliable trend as clinical fact.

    Harm types:
    - Unnecessary clinic visit (false positive alert)
    - Delayed real action (false negative / ignored valid trend)
    - Resource waste and patient anxiety
    """
    costs = HARM_COSTS
    items: list[dict] = []
    total = 0.0

    # Scenario 1: False Positive Alert Harm
    # If a concerning trend is acted upon when data reliability is low (<70), costs scale
    # proportionally with unreliability (1 - reliability/100).
    if trend.concerning and reliability.score < 70:
        # Acting on unreliable concerning trend → false alarm harm
        visit_harm = costs.unnecessary_clinic_visit * (1 - reliability.score / 100)
        anxiety = costs.patient_anxiety * (1 - reliability.score / 100)
        resource = costs.resource_waste_per_false_alert * (1 - reliability.score / 100)
        items.extend([
            {"type": "unnecessary_clinic_visit", "score": round(visit_harm, 2),
             "reason": "Concerning trend flagged but data reliability insufficient"},
            {"type": "patient_anxiety", "score": round(anxiety, 2),
             "reason": "False alarm may cause undue stress in remote setting"},
            {"type": "resource_waste", "score": round(resource, 2),
             "reason": "Clinic capacity limited; false alerts drain resources"},
        ])
        total += visit_harm + anxiety + resource

    # Scenario 2: Indecision / Delay Risk
    # Adequate reliability (>=70) and concerning trend, but low trend statistical confidence (<60)
    if trend.concerning and reliability.score >= 70 and uncertainty.confidence < 60:
        delay = costs.delayed_real_action * 0.3
        items.append({
            "type": "delayed_action_risk", "score": round(delay, 2),
            "reason": "Moderate confidence may delay needed follow-up",
        })
        total += delay

    # Scenario 3: Masked Emergence / False Negative Risk
    # Severe data degradation (<50) with no trend detected: gaps or outages may hide a real acute event
    if not trend.concerning and reliability.score < 50:
        miss_risk = costs.delayed_real_action * 0.5
        items.append({
            "type": "missed_trend_risk", "score": round(miss_risk, 2),
            "reason": "Safe fallback may mask emerging trend; schedule re-check",
        })
        total += miss_risk

    if items:
        recommendation = (
            "Do not schedule clinic visit based on current data. "
            "Request 3 consecutive daily device readings or health worker verification."
        )
    else:
        recommendation = "Harm risk low at current reliability and trend confidence."

    return HarmAssessment(
        patient_id=reliability.patient_id,
        metric=reliability.metric,
        total_harm_score=round(total, 2),
        harm_items=items,
        recommendation=recommendation,
    )
