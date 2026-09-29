# Review 2 biometric thresholds

Screening bands for remote monitoring — not a diagnosis.

| Parameter | Unit | Risk | Range | Action |
|-----------|------|------|-------|--------|
| systolic_bp | mmHg | low | [−∞, 140) | Continue routine remote monitoring |
| systolic_bp | mmHg | medium | [140, 160) | Repeat BP within 15–30 min; schedule clinical review |
| systolic_bp | mmHg | high | [160, +∞) | Urgent clinical contact; do not wait for trend confirmation |
| diastolic_bp | mmHg | low | [−∞, 90) | Continue routine remote monitoring |
| diastolic_bp | mmHg | medium | [90, 110) | Repeat BP; assess symptoms (headache, visual change, edema) |
| diastolic_bp | mmHg | high | [110, +∞) | Urgent clinical contact for severe-range diastolic BP |
| blood_glucose_mgdl | mg/dL | low | [−∞, 95) | Routine nutrition counseling |
| blood_glucose_mgdl | mg/dL | medium | [95, 126) | Repeat fasting glucose; consider GDM workup pathway |
| blood_glucose_mgdl | mg/dL | high | [126, +∞) | Escalate for diagnostic testing / diabetes care pathway |
| heart_rate | bpm | medium | [−∞, 60) | Bradycardia — repeat and correlate with symptoms |
| heart_rate | bpm | low | [60, 100) | Routine monitoring |
| heart_rate | bpm | medium | [100, 120) | Assess fever, dehydration, anemia, anxiety; repeat |
| heart_rate | bpm | high | [120, +∞) | Urgent review if persistent with symptoms |
| hrv_rmssd_ms | ms | high | [−∞, 15) | Flag reduced HRV with other abnormal vitals only |
| hrv_rmssd_ms | ms | medium | [15, 20) | Watch with BP/HR; not independently actionable |
| hrv_rmssd_ms | ms | low | [20, +∞) | No isolated HRV action |
| weight_gain | kg/week | low | [−∞, 0.7) | Within typical weekly gain for many pregnancies |
| weight_gain | kg/week | medium | [0.7, 1.0) | Counsel on fluid retention vs excess gain; re-weigh |
| weight_gain | kg/week | high | [1.0, +∞) | Evaluate rapid gain with BP (edema / preeclampsia context) |

## References
- systolic_bp: ACOG Practice Bulletin 222 / ISSHP 2021 — 140/90 and 160/110 bands
- diastolic_bp: ACOG / ISSHP — diastolic 90 and 110 mmHg bands
- blood_glucose_mgdl: ADA Standards of Care; IADPSG fasting 92–95 mg/dL screening context (home proxy)
- heart_rate: Clinical tachycardia thresholds (100 / 120 bpm) — nonspecific
- hrv_rmssd_ms: Time-domain HRV literature (RMSSD); adjunct only, not a diagnostic standard
- weight_kg: National Academy of Medicine gestational weight-gain guidance (weekly rate proxy)
- fetal_movement: Cardiff count-to-ten / reduced-fetal-movement guidance (home kick-count proxy)
- temperature_c: Maternal fever screening (≥38.0 °C); isolated fever is nonspecific
- spo2_pct: Pulse-oximetry hypoxemia bands (<92% / 92–95%); home SpO2 is a screening proxy
