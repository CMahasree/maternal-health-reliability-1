"""Multi-parameter maternal risk scoring for Review 2.

Uses Review 1 reliability as a safety gate so noisy or missing data cannot
silently become a confident high-risk action.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from maternal_reliability.pipeline.orchestrator import assess_patient
from maternal_reliability.pipeline.trend_detection import detect_trend
from maternal_reliability.review2.thresholds import (
    BLOOD_GLUCOSE_MGDL,
    DIASTOLIC_BP_MMHG,
    FETAL_MOVEMENT_COUNT,
    HEART_RATE_BPM,
    HRV_RMSSD_MS,
    RISK_ACTIONS,
    SEVERITY,
    SPO2_PCT,
    SYSTOLIC_BP_MMHG,
    TEMPERATURE_C,
    WEIGHT_GAIN_KG_PER_WEEK,
    band_for_value,
)


@dataclass
class ParameterContribution:
    metric: str
    value: float | None
    band: str | None
    action: str


@dataclass
class RiskResult:
    patient_id: str
    predicted_risk: str
    risk_points: int
    reliability_score: float
    reliability_gated: bool
    alert: bool
    action: str
    contributions: list[ParameterContribution] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)


def _recent_median(df: pd.DataFrame, patient_id: str, metric: str, days: int = 7) -> float | None:
    subset = df[(df["patient_id"] == patient_id) & (df["metric"] == metric)].copy()
    if subset.empty:
        return None
    subset["timestamp"] = pd.to_datetime(subset["timestamp"], utc=True)
    end = subset["timestamp"].max()
    window = subset[subset["timestamp"] >= end - pd.Timedelta(days=days)]
    if window.empty:
        window = subset.tail(3)
    if "quality_label" in window.columns:
        clean = window[window["quality_label"] != "bad"]
        if not clean.empty:
            window = clean
    if window.empty:
        return None
    return float(window["value"].median())


def _weekly_weight_gain(df: pd.DataFrame, patient_id: str) -> float | None:
    subset = df[(df["patient_id"] == patient_id) & (df["metric"] == "weight_kg")].copy()
    if len(subset) < 2:
        return None
    subset["timestamp"] = pd.to_datetime(subset["timestamp"], utc=True)
    subset = subset.sort_values("timestamp")
    t0 = subset["timestamp"].iloc[0]
    days = (subset["timestamp"].iloc[-1] - t0).total_seconds() / 86400.0
    if days < 6:
        return None
    gain = float(subset["value"].iloc[-1] - subset["value"].iloc[0])
    return gain / (days / 7.0)


def score_risk(df: pd.DataFrame, patient_id: str) -> RiskResult:
    """Combine Review 2 biometrics with reliability gating (Review 1 scorer unchanged)."""
    reliability = assess_patient(df, patient_id, "systolic_bp")
    contribs: list[ParameterContribution] = []
    rationale: list[str] = []
    max_sev = 1
    points = 0

    sbp = _recent_median(df, patient_id, "systolic_bp")
    dbp = _recent_median(df, patient_id, "diastolic_bp")
    glu = _recent_median(df, patient_id, "blood_glucose_mgdl")
    hr = _recent_median(df, patient_id, "heart_rate")
    hrv = _recent_median(df, patient_id, "hrv_rmssd_ms")
    fm = _recent_median(df, patient_id, "fetal_movement")
    temp = _recent_median(df, patient_id, "temperature_c")
    spo2 = _recent_median(df, patient_id, "spo2_pct")
    wt_gain = _weekly_weight_gain(df, patient_id)

    pairs = [
        ("systolic_bp", sbp, SYSTOLIC_BP_MMHG),
        ("diastolic_bp", dbp, DIASTOLIC_BP_MMHG),
        ("blood_glucose_mgdl", glu, BLOOD_GLUCOSE_MGDL),
        ("heart_rate", hr, HEART_RATE_BPM),
        ("hrv_rmssd_ms", hrv, HRV_RMSSD_MS),
        ("fetal_movement", fm, FETAL_MOVEMENT_COUNT),
        ("temperature_c", temp, TEMPERATURE_C),
        ("spo2_pct", spo2, SPO2_PCT),
    ]
    for name, value, bands in pairs:
        band = band_for_value(bands, value)
        if band is None:
            contribs.append(ParameterContribution(name, value, None, "Parameter missing"))
            rationale.append(f"{name}: missing")
            continue
        contribs.append(ParameterContribution(name, value, band.name, band.action))
        sev = SEVERITY[band.name]
        max_sev = max(max_sev, sev)
        points += {1: 0, 2: 2, 3: 5}[sev]
        if band.name != "low":
            rationale.append(f"{name}={value:.1f} → {band.name}")

    wt_band = band_for_value(WEIGHT_GAIN_KG_PER_WEEK, wt_gain) if wt_gain is not None else None
    contribs.append(
        ParameterContribution(
            "weight_gain_kg_per_week",
            wt_gain,
            wt_band.name if wt_band else None,
            wt_band.action if wt_band else "Insufficient weigh-ins",
        )
    )
    if wt_band:
        max_sev = max(max_sev, SEVERITY[wt_band.name])
        points += {1: 0, 2: 1, 3: 3}[SEVERITY[wt_band.name]]
        if wt_band.name != "low":
            rationale.append(f"weight gain {wt_gain:.2f} kg/week → {wt_band.name}")

    for metric in ("systolic_bp", "diastolic_bp", "blood_glucose_mgdl"):
        trend = detect_trend(df, patient_id, metric)
        if trend.concerning:
            points += 2
            rationale.append(f"concerning {metric} trend (slope {trend.slope_per_day}/day)")

    if points >= 8 or max_sev >= 3:
        predicted = "high"
    elif points >= 3 or max_sev >= 2:
        predicted = "medium"
    else:
        predicted = "low"

    gated = False
    if reliability.reliability.score < 50:
        gated = True
        predicted = "indeterminate"
        rationale.append(
            f"reliability {reliability.reliability.score} < 50 — safe fallback, no risk action"
        )
    elif reliability.reliability.score < 70 and predicted == "high":
        # Severe-range BP with moderate reliability stays high; otherwise step down.
        sbp_band = band_for_value(SYSTOLIC_BP_MMHG, sbp)
        dbp_band = band_for_value(DIASTOLIC_BP_MMHG, dbp)
        severe = (sbp_band and sbp_band.name == "high") or (dbp_band and dbp_band.name == "high")
        if not severe:
            gated = True
            predicted = "medium"
            rationale.append("high-risk stepped down: reliability < 70 without severe-range BP")

    alert = predicted == "high"
    return RiskResult(
        patient_id=patient_id,
        predicted_risk=predicted,
        risk_points=points,
        reliability_score=reliability.reliability.score,
        reliability_gated=gated,
        alert=alert,
        action=RISK_ACTIONS[predicted],
        contributions=contribs,
        rationale=rationale or ["All available parameters in low-risk bands"],
    )
