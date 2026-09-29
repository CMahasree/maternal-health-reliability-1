"""Clinical biometric thresholds for Review 2 multi-parameter risk scoring.

References are guideline-level screening bands for remote monitoring, not
diagnostic criteria. They are documented so Review 2 results can be audited.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    """Inclusive lower bound, exclusive upper bound unless upper is None."""

    name: str  # low | medium | high
    low: float | None
    high: float | None
    action: str


# ACOG / ISSHP hypertensive disorders in pregnancy (office/home cuff bands).
# Severe-range BP is treated as high risk even from a single confirmed window.
SYSTOLIC_BP_MMHG = [
    Band("low", None, 140, "Continue routine remote monitoring"),
    Band("medium", 140, 160, "Repeat BP within 15–30 min; schedule clinical review"),
    Band("high", 160, None, "Urgent clinical contact; do not wait for trend confirmation"),
]

DIASTOLIC_BP_MMHG = [
    Band("low", None, 90, "Continue routine remote monitoring"),
    Band("medium", 90, 110, "Repeat BP; assess symptoms (headache, visual change, edema)"),
    Band("high", 110, None, "Urgent clinical contact for severe-range diastolic BP"),
]

# ADA / IADPSG fasting plasma glucose screening bands (mg/dL).
# Home glucometer values are a screening proxy, not a diagnostic OGTT.
BLOOD_GLUCOSE_MGDL = [
    Band("low", None, 95, "Routine nutrition counseling"),
    Band("medium", 95, 126, "Repeat fasting glucose; consider GDM workup pathway"),
    Band("high", 126, None, "Escalate for diagnostic testing / diabetes care pathway"),
]

# Resting maternal heart rate (bpm). Tachycardia is nonspecific.
HEART_RATE_BPM = [
    Band("medium", None, 60, "Bradycardia — repeat and correlate with symptoms"),
    Band("low", 60, 100, "Routine monitoring"),
    Band("medium", 100, 120, "Assess fever, dehydration, anemia, anxiety; repeat"),
    Band("high", 120, None, "Urgent review if persistent with symptoms"),
]

# Time-domain HRV proxy (RMSSD, ms). Reduced HRV is a nonspecific stress marker.
HRV_RMSSD_MS = [
    Band("high", None, 15, "Flag reduced HRV with other abnormal vitals only"),
    Band("medium", 15, 20, "Watch with BP/HR; not independently actionable"),
    Band("low", 20, None, "No isolated HRV action"),
]

# Gestational weight: Review 2 uses weekly gain, not pre-pregnancy BMI (unknown).
# IOM-informed: sustained >1.0 kg/week is excessive for most BMI groups.
WEIGHT_GAIN_KG_PER_WEEK = [
    Band("low", None, 0.7, "Within typical weekly gain for many pregnancies"),
    Band("medium", 0.7, 1.0, "Counsel on fluid retention vs excess gain; re-weigh"),
    Band("high", 1.0, None, "Evaluate rapid gain with BP (edema / preeclampsia context)"),
]

# Daily fetal-movement count proxy (Cardiff/count-to-ten style home log, not a CTG).
FETAL_MOVEMENT_COUNT = [
    Band("high", None, 6, "Reduced fetal movement — same-day clinical contact"),
    Band("medium", 6, 10, "Repeat kick count; advise when to present"),
    Band("low", 10, None, "Routine fetal-movement awareness"),
]

# Maternal oral/axillary temperature (°C). Isolated low-grade fever is nonspecific.
TEMPERATURE_C = [
    Band("low", None, 38.0, "Afebrile screening range"),
    Band("medium", 38.0, 38.5, "Low-grade fever — repeat; assess infection / chorioamnionitis risk"),
    Band("high", 38.5, None, "Fever — urgent clinical review"),
]

# Pulse oximetry (%). Home SpO2 is a screening proxy, not arterial blood gas.
SPO2_PCT = [
    Band("high", None, 92.0, "Hypoxemia range — urgent review"),
    Band("medium", 92.0, 95.0, "Borderline saturation — repeat on room air; assess dyspnea"),
    Band("low", 95.0, None, "Routine SpO2 monitoring"),
]

RISK_ACTIONS = {
    "low": "Routine remote follow-up; no extra clinic slot",
    "medium": "Confirmatory reading + care-coordinator review within 24–48h",
    "high": "Clinical escalation; do not suppress on a single noisy channel if BP severe-range and data reliable",
    "indeterminate": "Safe fallback — collect confirmatory vitals before risk action",
}

PARAMETER_REFERENCES = {
    "systolic_bp": "ACOG Practice Bulletin 222 / ISSHP 2021 — 140/90 and 160/110 bands",
    "diastolic_bp": "ACOG / ISSHP — diastolic 90 and 110 mmHg bands",
    "blood_glucose_mgdl": "ADA Standards of Care; IADPSG fasting 92–95 mg/dL screening context (home proxy)",
    "heart_rate": "Clinical tachycardia thresholds (100 / 120 bpm) — nonspecific",
    "hrv_rmssd_ms": "Time-domain HRV literature (RMSSD); adjunct only, not a diagnostic standard",
    "weight_kg": "National Academy of Medicine gestational weight-gain guidance (weekly rate proxy)",
    "fetal_movement": "Cardiff count-to-ten / reduced-fetal-movement guidance (home kick-count proxy)",
    "temperature_c": "Maternal fever screening (≥38.0 °C); isolated fever is nonspecific",
    "spo2_pct": "Pulse-oximetry hypoxemia bands (<92% / 92–95%); home SpO2 is a screening proxy",
}


def band_for_value(bands: list[Band], value: float | None) -> Band | None:
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return None
    for band in bands:
        lo_ok = band.low is None or value >= band.low
        hi_ok = band.high is None or value < band.high
        if lo_ok and hi_ok:
            return band
    return bands[-1]


SEVERITY = {"low": 1, "medium": 2, "high": 3, "indeterminate": 0}
