# Review 2 Evaluation Report

Generated from `python experiments/run_review2.py`. Review 1 code and the original 8-profile experiment path were not replaced.

## Scope (1–2 people, weeks not months)

| In Review 2 | Deferred |
|-------------|----------|
| 180 simulated profiles, multi-parameter scoring, subgroup metrics | Prospective de-identified clinic data |
| Documented clinical threshold bands | Diagnostic OGTT / BMI-specific weight charts |
| Laptop proxy latency, tracemalloc RAM, measured process CPU, source size | Hardware farm / Android SoC traces |
| Separate online / intermittent / offline scoring slices | Packet-level WAN emulator |

## Who this is for

- **Clinical partners:** high-risk recall, confusion matrix, when the system refuses to act (indeterminate).
- **Engineering:** latency, CPU, local/offline scoring, reliability gate.
- **Board / investors:** Review 1 8-profile headline is **not** the Review 2 claim; this round shows where performance drops.

## Review 1 (original 8 profiles, re-measured)

- n = 8
- Task = `alert_on_reliable_concerning_systolic_trend`
- Accuracy = **100.0%** (TP=2, FP=0, FN=0, TN=6)
- Precision = 1.0, recall = 1.0, F1 = 1.0
- Review 1 headline accuracy on 8 simulated profiles. Any 99.1% figure from a small-n demo does not carry into Review 2.

## Review 2 headline (180 profiles)

- Clinical 3-class accuracy = **91.7%** (indeterminate counts as a miss against low/medium/high)
- Macro-F1 (low/medium/high) = **0.899**
- Safety-aware accuracy (corner cases labeled indeterminate) = **78.9%**
- High-risk precision = 0.6757, high-risk recall = 1.0, high-risk F1 = 0.8065
- Readings scored = 38965; wall clock = 19.8525s

### Per-class (clinical ground truth)

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|----|---------|
| low | 1.000 | 0.842 | 0.914 | 95 |
| medium | 0.952 | 1.000 | 0.976 | 60 |
| high | 0.676 | 1.000 | 0.806 | 25 |

### Confusion matrix (rows = true clinical risk, columns = predicted)

Labels: low, medium, high, indeterminate

```
[[80, 3, 12, 0], [0, 60, 0, 0], [0, 0, 25, 0], [0, 0, 0, 0]]
```

### Metrics by category

| Category | n | Accuracy | Macro-F1 | High-risk recall | High-risk precision |
|----------|---|----------|----------|------------------|---------------------|
| corner_case | 8 | 1.000 | 1.000 | 0.000 | 0.000 |
| high_risk | 25 | 1.000 | 1.000 | 1.000 | 1.000 |
| low_risk | 20 | 0.850 | 0.919 | 0.000 | 0.000 |
| medium_risk | 60 | 1.000 | 1.000 | 0.000 | 0.000 |
| missing_data | 15 | 1.000 | 1.000 | 0.000 | 0.000 |
| noisy_data | 12 | 0.000 | 0.000 | 0.000 | 0.000 |
| normal | 40 | 1.000 | 1.000 | 0.000 | 0.000 |

## Device / connectivity (laptop proxy)

- Mean / p50 / p95 / max latency: 249.052 / 246.106 / 325.412 / 369.576 ms
- Peak traced RAM: 0.881 MB; process RSS: 180.67 MB
- CPU: 41.3906 s process time; 92.33% of one logical CPU during the timed loop (16 logical CPUs). Process CPU seconds (Windows GetProcessTimes user+kernel, or Unix rusage, else time.process_time) divided by wall clock. cpu_percent is utilization of one logical CPU during the timed window.
- Package source size: 95.6 KB
- Offline capable: True — Scoring is fully local (no network call). Online, intermittent, and offline are scored as three separate data slices. Intermittent and offline are never merged into one ablation.
- Readings by connectivity tag: online=31001, intermittent=4775, offline=3189

### Connectivity scenarios (measured separately)

| Scenario | n readings | Batch s | ms/patient | Label change vs full mixed | Label change vs online baseline | Indeterminate |
|----------|------------|---------|------------|----------------------------|---------------------------------|---------------|
| online baseline | 31001 | 12.8108 | 71.171 | 0.0167 (3 patients) | — | 0 |
| intermittent | 4775 | 8.8109 | 48.95 | 0.4833 (87 patients) | 0.4889 (88 patients) | 83 |
| offline | 3189 | 8.1533 | 45.296 | 0.8611 (155 patients) | 0.8611 (155 patients) | 154 |

**Stakeholder tradeoff:** For this product and timeline, **offline scoring + high-risk recall** matter more than squeezing CPU. CPU is measured (process time / wall time) so the cost is visible; the scorer is still rule-based and RAM/model-size are not the binding constraint. Intermittent and offline slices are reported separately because they are different failure modes.

## Review 1 vs Review 2 (measured only)

- Review 1 task: `alert_on_reliable_concerning_systolic_trend`
- Review 2 task: 3-class plus indeterminate maternal risk on the Review 2 cohort

| Metric | Review 1 | Review 2 | Directly comparable | Note |
|--------|----------|----------|---------------------|------|
| sample_size | 8 | 180 | no | Review 1 evaluated 8 hand-built scenarios; Review 2 evaluated an expanded cohort of 180 simulated profiles across 10 clinical and edge-case scenarios. |
| accuracy | 1.0 | 0.9167 | no | Review 1 is binary alert-on-reliable-systolic-trend; Review 2 is 3-class clinical risk (indeterminate counts as a miss). |
| precision | 1.0 | 0.6757 | no | Review 1 precision is for the binary alert class; Review 2 is high-risk class precision. |
| recall | 1.0 | 1.0 | no | Review 1 recall is for the binary alert class; Review 2 is high-risk class recall. |
| f1 | 1.0 | 0.8065 | no | Review 1 F1 is the binary alert harmonic mean; Review 2 is high-risk F1. Macro-F1 (low/medium/high) is Review 2 only. |
| macro_f1_clinical | not measured | 0.8988 | no | Review 2 only: unweighted harmonic mean across low, medium, and high clinical risk classes. Review 1 had no 3-class macro-F1. |
| mean_latency_ms | 52.195 | 249.052 | no | Both measured on benchmark hardware: Review 1 times assess_patient (single-metric systolic reliability pipeline) and Review 2 times score_risk (9-biometric screening). |
| p95_latency_ms | 139.618 | 325.412 | no | 95th percentile per-patient latency on benchmark hardware. |
| peak_traced_ram_mb | 0.207 | 0.881 | no | Peak heap memory allocation traced via tracemalloc; workloads differ (8 vs 180 profiles; different functions). |
| process_rss_mb | 164.75 | 180.67 | no | Process resident set size (working set) in MB measured via OS process API during execution. |
| cpu_time_s | 0.2969 | 41.3906 | no | Measured process CPU seconds (user + kernel) consumed during each benchmark loop; not comparable across different n and functions. |
| cpu_percent | 71.09 | 92.33 | no | Single-core CPU utilization percentage during benchmark execution (cpu_time / wall_time * 100). |
| connectivity_online_label_change_rate_vs_full | not measured | 0.0167 | no | Review 1 has no separated connectivity ablation. Review 2: online-only live sync slice vs full mixed store. |
| connectivity_intermittent_label_change_rate_vs_online | not measured | 0.4889 | no | Review 2 only: intermittent-only delivery slice vs online baseline. |
| connectivity_offline_label_change_rate_vs_online | not measured | 0.8611 | no | Review 2 only: offline-only local cache slice vs online baseline. |

## Why Review 2 differs from Review 1

Review 1 tested alert-on-reliable-systolic-trend on 8 hand-built stories. Review 2 tests 3-class (plus indeterminate) risk on 180 profiles including missing, noisy, conflicting, reduced fetal movement, and fever data, using SBP, DBP, glucose, HR, HRV, weight gain, fetal movement, temperature, and SpO2. Accuracy is expected to fall; that is the result, not a failure of the experiment.

Figures: `metrics_by_category.png`, `confusion_clinical.png`, `latency_vs_connectivity.png`, `connectivity_impact.png`.

## Threshold references

- **systolic_bp:** ACOG Practice Bulletin 222 / ISSHP 2021 — 140/90 and 160/110 bands
- **diastolic_bp:** ACOG / ISSHP — diastolic 90 and 110 mmHg bands
- **blood_glucose_mgdl:** ADA Standards of Care; IADPSG fasting 92–95 mg/dL screening context (home proxy)
- **heart_rate:** Clinical tachycardia thresholds (100 / 120 bpm) — nonspecific
- **hrv_rmssd_ms:** Time-domain HRV literature (RMSSD); adjunct only, not a diagnostic standard
- **weight_kg:** National Academy of Medicine gestational weight-gain guidance (weekly rate proxy)
- **fetal_movement:** Cardiff count-to-ten / reduced-fetal-movement guidance (home kick-count proxy)
- **temperature_c:** Maternal fever screening (≥38.0 °C); isolated fever is nonspecific
- **spo2_pct:** Pulse-oximetry hypoxemia bands (<92% / 92–95%); home SpO2 is a screening proxy
- **Action [low]:** Routine remote follow-up; no extra clinic slot
- **Action [medium]:** Confirmatory reading + care-coordinator review within 24–48h
- **Action [high]:** Clinical escalation; do not suppress on a single noisy channel if BP severe-range and data reliable
- **Action [indeterminate]:** Safe fallback — collect confirmatory vitals before risk action
