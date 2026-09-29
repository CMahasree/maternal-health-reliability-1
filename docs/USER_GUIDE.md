# User Guide for Care Teams & Evaluators

## 1. System Overview & Core Philosophy

The **Maternal Health Data Reliability Scorer** is an automated clinical data-quality gatekeeper designed for remote and underserved maternal health settings. In remote monitoring, device dropouts, intermittent connectivity, irregular observation intervals, patient manual reporting errors, and sensor malfunctions can create deceptive physiological trends.

The primary mission of this system is **transparency over raw prediction**:
- It evaluates whether available maternal telemetry is **sufficiently reliable for clinical review**.
- It provides an explicit **audit evidence chain** connecting individual readings to data-quality scores.
- It enforces a **safe operational fallback** when data integrity is compromised.

---

## 2. Explicit System Boundaries: What the System Does NOT Do

> [!CAUTION]
> **Strict Non-Diagnostic Scope:**
> 1. **No Medical Diagnosis**: This software does **NOT** diagnose preeclampsia, gestational diabetes, hypertension, maternal sepsis, or any other pathological condition.
> 2. **No Treatment Recommendations**: The system does **NOT** prescribe, recommend, or adjust dosages of medications (e.g. antihypertensives, insulin).
> 3. **No Clinical Judgment Replacement**: The software does **NOT** replace human clinical assessment. It screens **data trustworthiness** so that care teams do not waste scarce resources investigating artifactual trends.
> 4. **No Automated Hospital Admissions**: The system never schedules invasive clinical interventions autonomously without care-team review.

---

## 3. Installation & Setup

### Prerequisites
- Python 3.10 or 3.11 installed.
- Git installed.

### Setup Instructions

```bash
# 1. Clone repository and navigate to root
git clone <repository_url>
cd maternal-health-reliability-main/maternal-health-reliability-main

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows:
.\.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# 4. Install dependencies in editable development mode
pip install -e ".[dev]"
```

---

## 4. Running the Interactive Streamlit Dashboard

The Streamlit dashboard allows care coordinators to inspect longitudinal reading timelines, score breakdowns, evidence chains, harm assessments, and safe fallback guidance.

```bash
# Launch dashboard using project script
python scripts/run_dashboard.py

# Alternatively, launch via streamlit module directly
streamlit run dashboard/app.py
```

The dashboard will open automatically in your browser at `http://localhost:8501`.

---

## 5. Generating & Managing Simulated Data

The project operates on simulated maternal health telemetry modeling realistic remote community conditions.

```bash
# Generate Review 1 baseline simulated dataset (8 profiles -> data/simulated_readings.csv)
python scripts/generate_data.py

# Generate Review 3 expanded evaluation cohort (200 profiles -> data/review3_readings.csv)
python experiments/run_review3.py
```

---

## 6. Running the Reliability Scorer Programmatically

You can invoke the reliability scorer directly from Python scripts:

```python
import pandas as pd
from maternal_reliability.pipeline.orchestrator import assess_patient, run_pipeline

# 1. Load validated readings
df = pd.read_csv("data/simulated_readings.csv", parse_dates=["timestamp"])

# 2. Run single patient-metric assessment
result = assess_patient(df, patient_id="P001", metric="systolic_bp")

print(f"Patient:           {result.patient_id}")
print(f"Reliability Score: {result.reliability.score}/100 ({result.reliability.label.value})")
print(f"Trend Direction:   {result.trend.direction} (slope={result.trend.slope_per_day}/day)")
print(f"Confidence:        {result.uncertainty.confidence}%")
print(f"Decision:          {result.decision.outcome.value}")
print(f"Alert:             {result.decision.alert}")
print(f"Safe Fallback:     {result.decision.fallback_actions}")

# 3. Run batch pipeline across all patients (respects 50-patient capacity limit)
batch = run_pipeline(df, metrics=["systolic_bp"])
print(f"Processed: {len(batch.assessments)} assessments; Truncated: {batch.truncated}")
```

---

## 7. Running Tests & Auditing Quality

```bash
# Run entire test suite (all 37 unit, integration, and edge-case tests)
pytest tests/ -v

# Run tests via virtual environment Python executable
.\.venv\Scripts\python.exe -m pytest tests/ -v

# Run specific test modules
pytest tests/test_quality_check.py -v
pytest tests/test_reliability_scorer.py -v
pytest tests/test_trend_detection.py -v
pytest tests/test_pipeline_integration.py -v
pytest tests/test_edge_cases.py -v
pytest tests/test_review2.py -v
pytest tests/test_review3.py -v

# Run test coverage audit
pytest --cov=src/maternal_reliability tests/ -v
```

---

## 8. Running Evaluation Experiments & Benchmarks

```bash
# 1. Run Review 1 edge cases & baseline comparison (8 profiles)
python experiments/run_experiments.py

# 2. Run Review 2 multi-parameter evaluation & connectivity ablation (180 profiles)
python experiments/run_review2.py

# 3. Run Review 3 expanded evaluation, benchmarks, and multi-biometric audit (200 profiles)
python experiments/run_review3.py
```

All execution outputs, benchmark numbers, and evaluation plots are saved to:
`experiments/results/review3/`.

---

## 9. Interpreting System Outputs

### 9.1 Reliability Score & Classification Bands

| Score Range | Category Band | Clinical Interpretation & System Protocol |
|---|---|---|
| **$\ge 85.0$** | **HIGH** | Telemetry has high completeness, regular timestamps, and source agreement. Trends can be evaluated with high confidence. |
| **$70.0 - 84.9$** | **MODERATE** | Adequate data density for clinical screening. Actionable if accompanied by statistically significant trend and confidence $\ge 60\%$. |
| **$50.0 - 69.9$** | **LOW (CAUTION)** | Data integrity compromised by gaps, timing jitter, or minor quality flags. Alerts suppressed; requires confirmatory re-check. |
| **$< 50.0$** | **UNRELIABLE** | Critical data corruption: severe outage ($>35\%$ missing), major source conflict, or sensor step anomaly. Hard safe fallback enforced. |

### 9.2 Trend Status
- **`direction`**: Categorized based on linear slope: `"rising"` ($>+0.05/\text{day}$), `"falling"` ($<-0.05/\text{day}$), `"stable"`, or `"insufficient_data"` ($n < 5$).
- **`concerning`**: `True` only if slope meets clinical threshold (e.g. $\ge 1.5\text{ mmHg/day}$ for SBP), $p < 0.05$, and correlation $|r| > 0.3$.

### 9.3 Uncertainty Quantification
- **`confidence` ($0 - 100\%$)**: Multiplicative product of data reliability and regression goodness-of-fit.
- **$\ge 75\%$ (High)**: Trend estimate reflects consistent underlying telemetry.
- **$50 - 74\%$ (Moderate)**: Borderline statistical significance or sparse observations; verify before clinical action.
- **$< 50\%$ (Low)**: Insufficient statistical support; never act on trend alone.

### 9.4 Evidence Chain
Every assessment provides an audit trail:
- **`score_breakdown`**: Individual component sub-scores (Completeness, Regularity, Source Agreement, Connectivity, Quality Flags).
- **`rationale`**: Plain-language bullets explaining why points were deducted.
- **`contributing_readings`**: List of raw `reading_id` UUID strings utilized in the calculation.

### 9.5 Safe Fallback Actions
When data reliability is insufficient ($<50$ or high uncertainty), the system prescribes safe operational actions:
1. **Verify Connectivity**: Contact patient to confirm home device is powered and syncing.
2. **Collect Consecutive Readings**: Request 3 daily readings at the same time each morning.
3. **Dispatch Community Health Worker**: Send community worker for manual cuff calibration.
4. **Suppress Inappropriate Referrals**: Do **NOT** schedule an emergency clinic transfer based on unverified telemetry.
