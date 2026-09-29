# Maternal Health Data Reliability Scorer

Production-ready system for assessing the reliability of maternal health monitoring trends in remote areas with device gaps, irregular timestamps, and manual entry conflicts.

## Quick Start

```bash
# Clone and enter project
cd maternal_health_reliability

# Create virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -e ".[dev]"

# Generate simulated dataset
python scripts/generate_data.py

# Run all tests
pytest tests/ -v

# Run experiments (edge cases + baseline comparison)
python experiments/run_experiments.py

# Review 2 stress test (180-profile cohort, multi-parameter risk, device benchmarks)
python experiments/run_review2.py

# Full end-to-end validation (data + experiments + tests)
python scripts/run_all.py

# Launch dashboard (single command)
python scripts/run_dashboard.py
```

## System Flow

```
Simulated Data → Quality Check → Reliability Score → Trend Detection
    → Uncertainty Quantification → Harm Assessment → Evidence → Decision + Safe Fallback
```

## Project Structure

```
maternal_health_reliability/
├── src/maternal_reliability/   # Core package
│   ├── config.py               # Thresholds, weights, operational limits
│   ├── data/                   # Schema and simulated data generator
│   ├── pipeline/               # Quality, scoring, trend, harm, decision
│   └── baseline/               # Reference baseline scorer
├── dashboard/app.py            # Streamlit operational dashboard
├── experiments/                # Edge cases and baseline comparison
├── tests/                      # Unit and integration tests
├── scripts/                    # Data generation and dashboard launcher
├── docs/                       # Architecture, schema, guides, risk register
├── data/                       # Generated CSV datasets
└── .github/workflows/ci.yml    # CI/CD pipeline
```

## Reliability Labels & Thresholds

| Score | Label | Decision |
|-------|-------|----------|
| ≥ 85 | High | Actionable if trend concerning |
| 70–84 | Moderate | Actionable with confidence check |
| 50–69 | Low | Caution — verify before action |
| < 50 | Unreliable | Safe fallback — no clinical action |

**Component weights:** Completeness (30%), Regularity (20%), Source Agreement (20%), Connectivity (15%), Quality Flags (15%).

See [docs/STAKEHOLDER_ASSUMPTIONS.md](docs/STAKEHOLDER_ASSUMPTIONS.md) for clinical reasoning.

## Baseline Comparison

The baseline scorer flags any concerning trend with ≤20% missing data. The enhanced scorer adds source conflict detection, connectivity analysis, quality flags, and harm assessment — reducing false positives on unreliable data.

Run `python experiments/run_experiments.py` for measured FP/FN comparison.

## Documentation

- [Testing & Error Boundaries](docs/TESTING.md)
- [Data Schema](docs/DATA_SCHEMA.md)
- [Architecture Diagram](docs/ARCHITECTURE.md)
- [Stakeholder Assumptions](docs/STAKEHOLDER_ASSUMPTIONS.md)
- [Risk Register](docs/RISK_REGISTER.md)
- [Experiment Report](docs/EXPERIMENT_REPORT.md)
- [Review 2 Report](docs/REVIEW2_REPORT.md)
- [Review 2 Thresholds](docs/REVIEW2_THRESHOLDS.md)
- [User Guide (Care Teams)](docs/USER_GUIDE.md)
- [Findings Summary](docs/FINDINGS_SUMMARY.md)

## Testing and Error Boundaries

The test suite contains **37 automated tests** across 7 modules validating unit components, integration workflows, edge-case failure resilience, Review 2 risk telemetry, and Review 3 expanded evaluation.

### Test Categories Overview
- **Unit Tests** (9 tests): Validate isolated logic such as coefficient-of-variation irregularity calculation, empty DataFrame resilience, timestamp error coercion, systolic BP threshold classification, and multi-class metrics helpers.
- **Integration Tests** (8 tests): Validate full pipeline execution (`run_pipeline`), audit trail evidence population, safe fallback triggering on multi-week outages, and 180-profile Review 2 cohort generation.
- **Edge-Case & Error Tests** (12 tests): Stress-test fault tolerance under 18-day sensor outages, manual-device reading conflicts (>10% divergence within 48h), and spurious sensor step-changes (>20% jumps), verifying that false positive alerts remain suppressed.
- **Review 2 Telemetry Tests** (3 tests): Verify CPU kernel/user seconds measurement, resident set size (RSS), 3-way separated connectivity ablation (`online_baseline`, `intermittent`, `offline`), and side-by-side comparative schemas.
- **Review 3 Evaluation & Telemetry Tests** (5 tests): Validate the expanded 200-profile cohort generation, suppression of alerts on ungrounded edge cases (<70), true alert generation on genuine concerning trends, multi-biometric reliability scoring, and hardware latency/memory telemetry.

### Implemented Error & Exception Boundaries
1. **Schema Validation (`data/schema.py`)**: `validate_dataframe()` checks for empty DataFrames (returns warning), missing required columns (raises `ValueError`), unparseable timestamps (coerced to `NaT` and dropped), non-numeric values (coerced to `NaN` and dropped), and unrecognized metrics (flagged via warning).
2. **Quality Checks (`pipeline/quality_check.py`)**: `check_quality()` handles missing patient/metric combinations with a zeroed safe report, guards against divide-by-zero during interval calculation, assigns default irregularity penalties when $n < 3$, suppresses jump detection when $n < 5$, and flags stale readings (>72h).
3. **Reliability Safety Caps (`pipeline/reliability_scorer.py`)**: Overrides weighted sum with hard score caps when sample size is insufficient (<3 readings $\rightarrow \le 40$), data is stale ($\le 55$), bad quality rate $>25\%$ ($\le 55$), source conflict exists ($\le 60$), missingness $>35\%$ ($\le 50$), or isolated sensor jumps occur ($\le 55$).
4. **Clinical Decision Fallback (`pipeline/decision.py`)**: When reliability $<50$, unconditionally assigns `SAFE_FALLBACK`, suppresses clinical alerts, and generates 4 specific recovery actions.
5. **Batch Orchestration (`pipeline/orchestrator.py`)**: `run_pipeline()` enforces capacity limits (truncating at 50 assessments) and wraps per-patient evaluation in `try ... except Exception`, appending failure messages to warnings without crashing the batch.
6. **Hardware Telemetry (`review2/benchmarks.py`)**: Employs multi-tier OS detection trying Windows `kernel32.GetProcessTimes` and `psapi.GetProcessMemoryInfo`, Unix `resource.getrusage`, with fallback to `time.process_time()`.

For complete test mapping, assertion tables, and limitations, see **[docs/TESTING.md](docs/TESTING.md)**.

## API Endpoints & Programmatic Interfaces

**This project does not expose HTTP API endpoints.** Data processing occurs through CLI scripts, the interactive Streamlit dashboard (`dashboard/app.py`), and direct Python library function calls.

The core programmatic API interfaces are:

### 1. `assess_patient(df, patient_id, metric="systolic_bp")`
- **Module**: `maternal_reliability.pipeline.orchestrator`
- **Purpose**: Runs the complete Review 1 reliability assessment pipeline for a single patient and metric.
- **Parameters**:
  - `df` (`pd.DataFrame`): Validated DataFrame of device readings.
  - `patient_id` (`str`): Unique patient identifier (e.g. `"P001"`).
  - `metric` (`str`, optional): Metric name to assess. Default: `"systolic_bp"`.
- **Returns**: `AssessmentResult` dataclass containing:
  - `quality` (`QualityReport`): Missing rate, irregularity, conflict details, sensor anomaly status.
  - `reliability` (`ReliabilityScore`): Score (0–100), label (`high`, `moderate`, `low`, `unreliable`), component weights, rationale.
  - `trend` (`TrendResult`): Direction (`rising`, `falling`, `stable`), daily slope, p-value, clinical concern flag.
  - `uncertainty` (`UncertaintyEstimate`): Confidence (0–100%), qualitative interval description, contributing factors.
  - `harm` (`HarmAssessment`): Total harm score, itemized harm penalties, recommendation.
  - `evidence` (`EvidenceChain`): Auditable summary, linked data points, score breakdown.
  - `decision` (`ClinicalDecision`): Outcome (`actionable`, `caution`, `not_actionable`, `safe_fallback`), alert flag (`bool`), fallback actions.
- **Error Behavior**: Propagates `ValueError` if DataFrame is malformed or missing required columns.

### 2. `run_pipeline(df, metrics=None, patient_ids=None)`
- **Module**: `maternal_reliability.pipeline.orchestrator`
- **Purpose**: Batch execution of the reliability pipeline across multiple patients and metrics.
- **Parameters**:
  - `df` (`pd.DataFrame`): DataFrame of maternal device readings.
  - `metrics` (`list[str] | None`): List of metrics to assess. Defaults to `["systolic_bp"]`.
  - `patient_ids` (`list[str] | None`): List of patient IDs. Defaults to all unique patients in `df`.
- **Returns**: `PipelineResult` dataclass containing:
  - `assessments` (`list[AssessmentResult]`): List of completed assessments.
  - `warnings` (`list[str]`): Validation warnings and per-patient failure logs.
  - `truncated` (`bool`): `True` if task count exceeded `OPERATIONAL_LIMITS.max_pending_assessments` (50).
- **Error Behavior**: Validates schema upfront (raising `ValueError` if required columns are absent). Individual patient execution failures are caught and recorded in `warnings`.

### 3. `score_risk(df, patient_id)`
- **Module**: `maternal_reliability.review2.risk_scorer`
- **Purpose**: Multi-parameter maternal risk evaluation across 9 biometrics with Review 1 reliability gating.
- **Parameters**:
  - `df` (`pd.DataFrame`): Full readings DataFrame.
  - `patient_id` (`str`): Target patient ID.
- **Returns**: `RiskResult` dataclass containing:
  - `predicted_risk` (`str`): `"low"`, `"medium"`, `"high"`, or `"indeterminate"` (safe fallback).
  - `risk_points` (`int`): Cumulative clinical risk points.
  - `reliability_score` (`float`): Systolic BP reliability score from Review 1 scorer.
  - `reliability_gated` (`bool`): `True` if reliability $<50$ (overridden to indeterminate) or $<70$ (high-risk stepped down to medium).
  - `alert` (`bool`): `True` only if final predicted risk is `"high"`.
  - `action` (`str`): Recommended clinical action text.
  - `contributions` (`list[ParameterContribution]`): Per-biometric values, risk bands, and clinical actions.
  - `rationale` (`list[str]`): Clinical rationale list.
- **Error Behavior**: Missing biometrics are handled gracefully (marked as missing without raising exceptions).

### 4. `check_quality(df, patient_id, metric)`
- **Module**: `maternal_reliability.pipeline.quality_check`
- **Purpose**: Evaluates temporal regularity, missing data rate, source conflict, stale status, and sensor step-changes.
- **Returns**: `QualityReport` dataclass.

### 5. `detect_trend(df, patient_id, metric, window_days=None, exclude_bad_quality=True)`
- **Module**: `maternal_reliability.pipeline.trend_detection`
- **Purpose**: Performs linear regression slope analysis and flags clinically concerning trajectories.
- **Returns**: `TrendResult` dataclass.

## Database Schema & Data Storage

This project **does not use an external SQL or NoSQL database server**. All persistent data is stored in versioned CSV and JSON files, and processed in-memory using pandas DataFrames and Python dataclasses.

### Persistent File Datasets

#### 1. Device Readings: `data/simulated_readings.csv`
Contains simulated longitudinal time-series readings with realistic gaps, timestamps, and error conditions.
- Primary Key (Logical): `reading_id`
- Foreign Key: `patient_id` (relates to `ground_truth_labels.csv`)

| Column Name | Type | Nullable | Description & Constraints |
|---|---|---|---|
| `reading_id` | `string` | No | Unique 8-character UUID string identifier for audit trail. |
| `patient_id` | `string` | No | Identifier for the patient (e.g. `"P001"`, `"P002"`). |
| `timestamp` | `datetime64[ns, UTC]` | No | UTC timestamp of observation; includes simulated jitter ($\pm 6$–$12\text{ h}$). |
| `metric` | `string` | No | Biometric name (`systolic_bp`, `diastolic_bp`, `heart_rate`, `weight_kg`, `fetal_movement`, etc.). |
| `value` | `float64` | No | Measured value in clinical units (mmHg, bpm, kg, kick count). |
| `source` | `string` | No | Measurement source: `"device"`, `"manual"`, or `"health_worker"`. |
| `device_id` | `string` | No | Device identifier string (e.g. `"DEV-P001-001"`). |
| `connectivity_status`| `string` | No | Device connection state: `"online"`, `"offline"`, or `"intermittent"`. |
| `quality_label` | `string` | No | Signal quality flag: `"good"`, `"suspect"`, `"bad"`, or `"missing_imputed"`. |
| `gap_before_hours` | `float64` | No | Elapsed hours since previous reading of the same metric for this patient. |
| `is_gap` | `bool` | No | `True` if `gap_before_hours > 2 * EXPECTED_INTERVAL_HOURS`. |
| `notes` | `string` | Yes | Annotations (e.g. manual conflict explanations). |
| `scenario` | `string` | No | Scenario tag (`stable_normal`, `multi_week_outage`, `sensor_malfunction`, etc.). |

#### 2. Ground Truth Labels: `data/ground_truth_labels.csv`
Reference labels for evaluating scorer accuracy and false positive/negative suppression.
- Primary Key: `patient_id`

| Column Name | Type | Nullable | Description |
|---|---|---|---|
| `patient_id` | `string` | No | Patient identifier matching `simulated_readings.csv`. |
| `scenario` | `string` | No | Simulation scenario name. |
| `ground_truth_reliable` | `bool` | No | Ground-truth flag: whether data has sufficient integrity for clinical action. |
| `ground_truth_alert` | `bool` | No | Ground-truth flag: whether an acute or escalating clinical condition is present. |

#### 3. Review 2 Cohort & Benchmark Artifacts: `experiments/results/review2/`
- `review2_predictions.csv`: 180-profile evaluation rows including `patient_id`, `scenario`, `category`, `y_true`, `y_pred`, `reliability_score`, `reliability_gated`, and `alert`.
- `review2_metrics.json`: Overall and per-class clinical accuracy, macro-F1, confusion matrices, and subgroup performance.
- `review1_snapshot.json`: Re-execution metrics of Review 1 on 8 baseline profiles.
- `review1_vs_review2.json`: Side-by-side comparison across 14 metrics with non-equivalence notes.

### Core In-Memory Data Models (Dataclasses)
- `ReadingRecord`: Structured single-reading record (`data/schema.py`).
- `QualityReport`: Intermediate quality metrics and anomaly flags (`pipeline/quality_check.py`).
- `ReliabilityScore`: Composite score (0–100), categorical label, and component dictionary (`pipeline/reliability_scorer.py`).
- `TrendResult`: Regression slope, p-value, direction, and evidence points (`pipeline/trend_detection.py`).
- `UncertaintyEstimate`: Combined confidence score and uncertainty factors (`pipeline/uncertainty.py`).
- `HarmAssessment`: Quantified cost penalties and safe mitigation recommendations (`pipeline/harm_assessment.py`).
- `EvidenceChain`: Audit trail connecting raw reading IDs to final decisions (`pipeline/evidence.py`).
- `ClinicalDecision`: Final operational outcome, alert boolean, and safe fallback instructions (`pipeline/decision.py`).
- `AssessmentResult`: Aggregated assessment container for one patient-metric (`pipeline/orchestrator.py`).
- `RiskResult`: Multi-parameter Review 2 risk result with reliability gating status (`review2/risk_scorer.py`).

## Test Execution

The project uses `pytest` for automated test discovery and execution.

### Commands to Run Tests

```bash
# Activate virtual environment (if not already activated)
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Run entire test suite (37 tests)
pytest tests/ -v

# Run with python module invocation
python -m pytest tests/ -v

# Run specific test modules
pytest tests/test_quality_check.py -v
pytest tests/test_reliability_scorer.py -v
pytest tests/test_pipeline_integration.py -v
pytest tests/test_edge_cases.py -v
pytest tests/test_review2.py -v
pytest tests/test_review3.py -v
pytest tests/test_trend_detection.py -v

# Run tests with code coverage report
pytest --cov=src/maternal_reliability tests/ -v
```

### What the Test Suite Covers
- **Coverage**: 100% of pipeline modules under `src/maternal_reliability/pipeline/`, `src/maternal_reliability/data/`, `src/maternal_reliability/review2/`, and `src/maternal_reliability/review3/`.
- **Total Test Count**: 37 passed test cases in ~14 seconds.
- **Edge cases covered**: 18-day outages, manual entry conflicts, spurious sensor steps (+35 mmHg), missing data rates, sample size depletion ($n < 3$ and $n < 5$), stale data (>72h), Review 2 multi-parameter risk classification, separate 3-way connectivity ablation, and Review 3 expanded 200-profile reliability screening.

## Operational Limits

| Parameter | Value |
|-----------|-------|
| Max pending assessments | 50 |
| Recheck interval | 24 hours |
| Stale data threshold | 72 hours |
| Max assessments/patient/day | 4 |

## License

MIT — for demonstration and educational use in maternal health monitoring research.
#
#   m a t e r n a l - h e a l t h - r e l i a b i l i t y - r e v i e w 3  
 