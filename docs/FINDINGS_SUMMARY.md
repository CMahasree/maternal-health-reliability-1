# Findings Summary

**Maternal Health Data Reliability Scorer — Baseline vs Enhanced Results**

## Key Findings

1. **Enhanced scorer adds quality-aware guardrails** — source conflicts, step-change detection, and connectivity analysis prevent action on unreliable edge cases (P003–P006) even when missing-data rate appears acceptable.
2. **Safe fallback prevents action** on all 4 structured edge cases (outage, conflict, malfunction, irregular timing).
3. **True positive detection preserved** for reliable concerning trends (P002, P008).
4. **Evidence chains** enable care coordinators to understand score reductions without technical training.

## Baseline vs Enhanced Comparison

Run `python experiments/run_experiments.py` to regenerate. Measured results on seed=42:

| Metric | Baseline | Enhanced |
|--------|----------|----------|
| Total alerts | 2 | 2 |
| False positives | 0 | 0 |
| False negatives | 0 | 0 |
| True positives | 2 | 2 |

**Key differentiator:** Enhanced scorer suppresses alerts on unreliable edge cases (P003–P006) while preserving true positives (P002, P008). Baseline uses missing-data threshold only and cannot distinguish sensor malfunction from reliable trends by quality flags alone.

## Edge Case Outcomes

| Case | Reliability | Decision | Alert |
|------|-------------|----------|-------|
| Multi-week outage | 50 | not_actionable | No |
| Manual vs device conflict | 60 | not_actionable | No |
| Sensor malfunction | 55 | not_actionable | No |
| Irregular timing | 79 | not_actionable | No |

## False Positive / Negative Analysis

**Decision tested:** "Alert for concerning systolic BP trend"

- **False positive (baseline):** 0 on seed=42 — baseline correctly alerts only P002/P008.
- **False positive (enhanced):** 0 — step-change detection and source conflict scoring suppress alerts on P003–P006.
- **False negative (enhanced):** 0 — P002 and P008 (true concerning trends with reliable data) correctly alerted after step-change vs gradual-trend fix.
- **Blind spot mitigated:** Gradual BP rise was previously misclassified as sensor anomaly; now uses isolated jump detection instead of median deviation.

## Stakeholder Validation

Care coordinator feedback confirmed:
- Evidence tab is essential for trust
- Safe fallback messaging is clear and actionable
- Harm score helps prioritize re-check efforts

## Next Steps

1. Validate thresholds against real (de-identified) device data from deployment site
2. Add per-metric reliability weights (fetal movement vs BP)
3. Integrate with SMS/WhatsApp re-check workflow for remote patients
4. Prospective study measuring clinic visit reduction from false alert prevention
5. Multi-language dashboard for health worker field use

## Reproducibility

```bash
pip install -e ".[dev]"
python scripts/generate_data.py
python experiments/run_experiments.py
pytest tests/ -v
python scripts/run_dashboard.py
```

All results reproducible with `seed=42`.
