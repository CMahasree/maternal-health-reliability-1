# Stakeholder Assumptions

Documented constraints and priorities that shaped system design. Validated through structured review with a **care coordinator** (simulated stakeholder session, August 2025).

## Care Team Constraints

1. **Limited clinic capacity**: Remote clinics serve 200+ patients with 2–3 staff; false alerts cause unnecessary 4-hour travel for patients.
2. **Connectivity**: 30–40% of patients experience intermittent device connectivity weekly.
3. **Health worker visits**: Occur every 2 weeks at best; manual readings may contradict device data.
4. **Decision timeline**: Care coordinators review dashboards once daily; assessments must be batch-processable (max 50 pending).

## Clinical Thresholds

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Concerning BP rise | ≥ 1.5 mmHg/day over 14 days | Approaches preeclampsia screening threshold |
| Concerning HR rise | ≥ 2.0 bpm/day | Flags potential infection or dehydration |
| Actionable reliability | ≥ 70/100 | Coordinator feedback: "I need to trust at least 7/10 readings" |
| Safe fallback | < 50/100 | "Below half, I'd rather call the patient than trust the trend" |

## Device Limitations

- Home BP cuffs report every 24h when online; actual interval varies ±6h.
- Weight scales used weekly; missing weigh-ins are common.
- Fetal movement counted every 2 days; subjective and often skipped.
- Sensor malfunctions produce sudden spikes (observed in 5–10% of device lifetimes).

## Safety Priorities (Ranked)

1. **Never act on clearly unreliable data** — false clinic visits harm patients in remote settings.
2. **Do not miss reliable concerning trends** — delayed preeclampsia detection is highest clinical risk.
3. **Show evidence, not just scores** — coordinators rejected black-box alerts in usability review.
4. **Quantify harm** — helps prioritize re-check vs escalation.

## Stakeholder Feedback (Care Coordinator Session)

> "I want to see *why* the score is low before I tell a patient to come in."
> — Care Coordinator, remote maternal health program

> "If the device was offline for two weeks, don't show me a trend line — show me what's missing."
> — Care Coordinator

**Usability changes made based on feedback:**
- Added Evidence Chain tab with contributing reading IDs
- Safe fallback banner with specific re-collection steps
- Baseline comparison tab to build trust in enhanced scorer
- Export assessment JSON for supervisor review

## Capacity & Scheduling

| Limit | Value |
|-------|-------|
| Max pending assessments | 50 |
| Recheck interval | 24 hours |
| Stale data cutoff | 72 hours |
| Max assessments per patient per day | 4 |
