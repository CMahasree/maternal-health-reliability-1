# User Guide for Care Teams

## Purpose

This dashboard helps you decide whether a maternal health trend is **reliable enough to act on**. It does not replace clinical judgment — it provides evidence and confidence levels to support safe decisions.

## Getting Started

1. Run `python scripts/run_dashboard.py` (or access deployed instance)
2. Select a **Patient** and **Metric** (default: systolic blood pressure)
3. Review the header metrics: Reliability Score, Confidence, Harm Score, Decision

## Reading the Dashboard

### Header Metrics

| Metric | What It Means | Action |
|--------|---------------|--------|
| Reliability Score (0–100) | How trustworthy the underlying data is | ≥ 70: may act; 50–69: verify; < 50: do not act |
| Confidence (%) | Combined data + trend confidence | ≥ 60 needed for actionable alert |
| Harm if Acted Upon | Estimated cost of acting on unreliable data | Higher = more risk of wasted visit/anxiety |
| Decision | System recommendation | See decision types below |

### Decision Types

- **ACTIONABLE** (green): Concerning trend with reliable data. Schedule clinical follow-up.
- **CAUTION** (yellow): Possible trend but insufficient confidence. Obtain confirmatory reading.
- **NOT ACTIONABLE** (blue): No concerning trend. Continue routine monitoring.
- **SAFE FALLBACK** (red): Data too unreliable. Do NOT act on trend. Follow fallback steps.

## Tab Guide

### Trend & Data
- Line chart of readings over time
- Table showing source, connectivity, quality flags, and gaps
- Trend statistics (slope, p-value, concerning flag)

### Evidence Chain
- Score breakdown by component (completeness, regularity, etc.)
- Rationale bullets explaining score reductions
- Contributing data point IDs for audit

### Harm Assessment
- Specific harm items if you acted on current data
- Safe fallback actions to improve data quality

### Baseline Comparison
- Shows what a simpler system would recommend vs this scorer
- Ground truth labels (in simulation) for training purposes

### All Patients
- Batch overview of all assessed patients
- Use for daily review workflow

## Safe Actions by Decision

### When SAFE FALLBACK
1. Call patient to check device connectivity
2. Request 3 consecutive daily readings
3. Schedule health worker visit if device unavailable
4. Do NOT schedule clinic visit based on current trend
5. Re-check in 24 hours

### When CAUTION
1. Request one confirmatory reading within 24h
2. Compare manual vs device if both available
3. Escalate to clinician only if second reading confirms

### When ACTIONABLE
1. Schedule clinic review within 48 hours
2. Document evidence chain in patient record
3. Export assessment JSON for supervisor

## Exporting Evidence

Use the sidebar **Download Assessment JSON** button to save the full evidence chain for patient records or supervisor review.

## What NOT to Do

- Do not override SAFE FALLBACK without new data
- Do not rely on trend line alone — check evidence tab
- Do not batch-schedule clinic visits from "All Patients" without individual review
