# Testing and Error Boundaries Specification

This document provides a technical audit of the test suite, assertion logic, exception handling, and error boundaries implemented in the `maternal-health-reliability` project.

---

## 1. Test Architecture & Environment

- **Test Framework**: `pytest` (v9.1.1 or higher)
- **Configuration**: `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["src"]`)
- **Total Test Modules**: 7 test files
- **Total Executable Tests**: 37 test cases (35 test functions, including 1 parametrized with 3 test cases)
- **Execution Engine**: Local Python 3.11 virtual environment (`.venv`)

---

## 2. Inventory of Test Modules

| Test Module Path | Test Count | Primary Validation Focus |
|------------------|------------|--------------------------|
| `tests/test_quality_check.py` | 7 | Data validation, missing data rates, timestamp regularity, 48h manual-device conflict detection, and sensor step-change detection. |
| `tests/test_reliability_scorer.py` | 4 | 5-component weighted reliability scoring (0–100), sample size constraints (<3), stale data caps, and safety capping behavior. |
| `tests/test_trend_detection.py` | 3 | Linear regression slope fitting, p-value / correlation significance criteria, minimum sample size requirements (>=5), and clinical slope evaluation. |
| `tests/test_pipeline_integration.py` | 5 | End-to-end data flow from raw DataFrame through quality, reliability, trend, uncertainty, harm, and decision outputs. |
| `tests/test_edge_cases.py` | 5 (3 parametrized + 2 analytical) | False positive / false negative behavior under multi-week outages, manual entry conflicts, and spurious sensor step-jumps against baseline reference. |
| `tests/test_review2.py` | 8 | Review 2 multi-parameter risk scoring across 9 biometrics, 180-profile synthetic cohort generation, CPU/RAM benchmark telemetry, and separated 3-way connectivity ablation. |
| `tests/test_review3.py` | 5 | Review 3 200-profile expanded cohort generation, rejection of unreliable scenarios (<70), concerning trend alerting, multi-biometric pipeline, and benchmarking telemetry. |

---

## 3. Categorized Test Suites & Assertion Analysis

The 37 test cases are structured into five functional groups:

### 3.1 Unit Tests (9 Tests)

These tests validate isolated algorithmic functions without executing the broader end-to-end pipeline.

| Test Function | Module | Key Assertions & Expected Behaviors |
|---|---|---|
| `test_check_quality_stable` | `test_quality_check.py` | Asserts `report.n_readings > 0`, `report.missing_rate < 0.3`, and `report.source_conflict is False` on standard 30-day baseline data. |
| `test_check_quality_empty` | `test_quality_check.py` | Passes empty DataFrame with required schema columns; asserts `report.n_readings == 0` and `report.missing_rate == 1.0` without raising unhandled exceptions. |
| `test_validate_malformed_timestamps` | `test_quality_check.py` | Passes DataFrame containing `"not-a-date"`; asserts bad row is dropped (`len(cleaned) == 1`) and `"malformed"` warning is recorded. |
| `test_high_reliability_stable` | `test_reliability_scorer.py` | Asserts stable normal data achieves composite score `>= 70` and maps to `HIGH` or `MODERATE` reliability labels. |
| `test_components_sum_weighted` | `test_reliability_scorer.py` | Asserts each component score in `score.components` falls in `[0, 100]` and `"completeness"` is present. |
| `test_concerning_trend_detected` | `test_trend_detection.py` | Asserts simulated escalating blood pressure yields `n_points >= 5`, `direction == "rising"`, and `concerning is True`. |
| `test_insufficient_data` | `test_trend_detection.py` | Asserts time series with only 3 observations yields `concerning is False` and `direction == "insufficient_data"`. |
| `test_sbp_bands` | `test_review2.py` | Validates clinical threshold binning for systolic BP: 120 mmHg (`low`), 150 mmHg (`medium`), 170 mmHg (`high`). |
| `test_metrics_helper` | `test_review2.py` | Validates custom multi-class metrics helper: verifies accuracy equals `2/3` and high-risk false negatives (`fn == 1`) match expected counts. |

---

### 3.2 Integration Tests (8 Tests)

These tests validate cross-module data flow, schema propagation, and multi-stage pipeline orchestration.

| Test Function | Module | Key Assertions & Expected Behaviors |
|---|---|---|
| `test_full_pipeline_runs` | `test_pipeline_integration.py` | Executes `run_pipeline` on full multi-patient dataset; asserts `len(result.assessments) > 0` and every assessment has a valid `decision.outcome`. |
| `test_safe_fallback_on_outage` | `test_pipeline_integration.py` | Evaluates patient `P003` (18-day outage); asserts decision outcome is non-actionable (`safe_fallback`, `caution`, or `not_actionable`) and `alert is False`. |
| `test_actionable_on_reliable_trend` | `test_pipeline_integration.py` | Evaluates patient `P002` (reliable hypertensive trend); asserts `reliability.score >= 50` and `trend.concerning is True`. |
| `test_baseline_vs_enhanced_differ_on_malfunction` | `test_pipeline_integration.py` | Evaluates patient `P005` (sensor malfunction); asserts enhanced scorer is more conservative than naive baseline (`alert is False` or `reliability.score < 70`). |
| `test_evidence_chain_populated` | `test_pipeline_integration.py` | Evaluates patient `P001`; asserts `evidence.summary != ""` and `evidence.score_breakdown` dictionary is populated. |
| `test_cohort_size` | `test_review2.py` | Validates generation of Review 2 cohort: asserts `COHORT_N == 180`, `len(labels) == 180`, scenario inclusion (`reduced_fetal_movement`, `maternal_fever`), and presence of all 3 connectivity states. |
| `test_high_risk_profile_flags_high` | `test_review2.py` | Evaluates synthetic high preeclampsia profile; asserts `predicted_risk in ("high", "medium")` and parameter contributions include `systolic_bp`. |
| `test_stable_profile_not_high` | `test_review2.py` | Evaluates stable normal Review 2 profile; asserts `predicted_risk in ("low", "indeterminate")`. |

---

### 3.3 Edge-Case & Error Boundary Tests (12 Tests)

These tests evaluate system resilience when handling corrupt, conflicting, or sparse telemetry.

| Test Function / Case | Module | Failure Scenario & Key Assertions |
|---|---|---|
| `test_edge_cases_no_false_alert[multi_week_outage-P003]` | `test_edge_cases.py` | 18-day sensor gap mid-series: asserts `assessment.decision.alert is False`. |
| `test_edge_cases_no_false_alert[manual_device_conflict-P004]` | `test_edge_cases.py` | Contradictory manual cuff entry: asserts `assessment.decision.alert is False`. |
| `test_edge_cases_no_false_alert[sensor_malfunction-P005]` | `test_edge_cases.py` | Sudden spurious step-change (+35 mmHg): asserts `assessment.decision.alert is False`. |
| `test_false_positive_analysis` | `test_edge_cases.py` | Compares enhanced scorer alerts against naive baseline on simulated cohort; asserts `enhanced_fp <= baseline_fp`. |
| `test_false_negative_analysis` | `test_edge_cases.py` | Asserts true alerts are preserved for genuine, reliable concerning trends without safety suppression. |
| `test_check_quality_outage` | `test_quality_check.py` | Asserts outage data produces `n_gaps >= 0` and elevated `missing_rate > 0.1`. |
| `test_manual_device_conflict` | `test_quality_check.py` | Evaluates manual entry diverging >10% from prior device reading within 48h; asserts `source_conflict is True` and `conflict_details != ""`. |
| `test_sensor_step_change_detected` | `test_quality_check.py` | Evaluates sudden +35 mmHg jump; asserts `sensor_anomaly is True` and `anomaly_details != ""`. |
| `test_gradual_trend_not_sensor_anomaly` | `test_quality_check.py` | Evaluates gradual clinical hypertension (+1.8 mmHg/day); asserts `sensor_anomaly is False` (gradual slope is not misclassified as sensor glitch). |
| `test_low_reliability_outage` | `test_reliability_scorer.py` | Asserts multi-week outage scores below actionable threshold (`score < 70`). |
| `test_unreliable_sensor_malfunction` | `test_reliability_scorer.py` | Asserts sensor malfunction caps reliability below 70 and emits explanatory rationale. |
| `test_sensor_malfunction_not_necessarily_concerning_with_few_bad` | `test_trend_detection.py` | Asserts bad readings exclusion prevents erroneous trend fitting on small subsets. |

---

### 3.4 Review 2 Performance & Hardware Telemetry Tests (3 Tests)

These tests evaluate Review 2 edge-computing constraints and benchmarking pipelines.

| Test Function | Module | Key Assertions & Expected Behaviors |
|---|---|---|
| `test_cpu_metric_is_measured` | `test_review2.py` | Measures in-process CPU seconds and RAM usage: asserts `cpu_time_s >= 0`, `cpu_percent >= 0`, `logical_cpus >= 1`, `process_rss_mb > 0`, and `process_cpu_seconds() >= 0`. |
| `test_connectivity_scenarios_are_separate` | `test_review2.py` | Asserts 3 distinct connectivity ablation slices (`online_baseline`, `intermittent`, `offline`), verifies `intermittent` and `offline` are compared against `online_baseline`, and confirms no merged offline/intermittent ablation key exists. |
| `test_side_by_side_comparison_structure` | `test_review2.py` | Validates Review 1 vs Review 2 comparative schema: asserts presence of 14 metrics (latency, RAM, CPU, connectivity drift) and confirms `directly_comparable is False` with explicit notes explaining methodology divergence. |

---

### 3.5 Review 3 Cohort, Reliability Screening & Multi-Biometric Tests (5 Tests)

These tests evaluate the expanded 200-profile cohort, data-reliability screening, and multi-biometric monitoring.

| Test Function | Module | Key Assertions & Expected Behaviors |
|---|---|---|
| `test_review3_cohort_size_and_schema` | `test_review3.py` | Validates 200-profile cohort generation: asserts `len(labels) == 200`, `len(readings) > 40000`, presence of all 9 scenarios, and existence of all 3 connectivity states and signal quality flags. |
| `test_review3_unreliable_scenarios_rejected` | `test_review3.py` | Validates that `multi_week_outage`, `manual_device_conflict`, and `sensor_malfunction` score below 70 (`score < 70`) and produce no clinical alert (`decision.alert is False`). |
| `test_review3_concerning_trend_actionable` | `test_review3.py` | Validates that `concerning_trend` achieves `reliability.score >= 70`, `trend.concerning is True`, and produces `decision.outcome == "actionable"` with `alert is True`. |
| `test_review3_multibiometric_pipeline` | `test_review3.py` | Validates multi-biometric execution across `systolic_bp`, `diastolic_bp`, `heart_rate`, `blood_glucose_mgdl`, and `weight_kg`: asserts positive reliability score and valid trend direction. |
| `test_review3_benchmarking_telemetry` | `test_review3.py` | Asserts benchmarking telemetry returns positive latency (`mean > 0`), measured peak RAM (`peak_traced_ram_mb > 0`), and valid environment metadata. |

---

## 4. Implemented Error & Exception Boundaries

The following table documents every active error boundary implemented in the codebase:

| Location | Guard / Handling Mechanism | Trigger Condition | System Behavior & Outcome |
|---|---|---|---|
| `schema.py` (`validate_dataframe`) | `if df.empty:` check | Empty DataFrame supplied | Returns `(df, ["Empty dataset provided"])` without raising exception. |
| `schema.py` (`validate_dataframe`) | `missing_cols` check | Missing required columns (`patient_id`, `timestamp`, `metric`, `value`, `source`) | Raises `ValueError(f"Missing required columns: {missing_cols}")`. |
| `schema.py` (`validate_dataframe`) | `pd.to_datetime(..., errors="coerce")` | Non-parseable or corrupt timestamp strings | Coerces to `NaT`, drops affected rows (`~bad_ts`), emits warning with dropped count. |
| `schema.py` (`validate_dataframe`) | `pd.to_numeric(..., errors="coerce")` | Non-numeric or corrupt measurement values | Coerces to `NaN`, drops affected rows (`~bad_val`), emits warning with dropped count. |
| `schema.py` (`validate_dataframe`) | `isin(KNOWN_METRICS)` | Unrecognized metric names | Retains rows but logs warning: `"Found N rows with unknown metrics (kept but flagged)"`. |
| `quality_check.py` (`check_quality`) | `if subset.empty:` check | Patient ID or metric not found in DataFrame | Returns zeroed `QualityReport` (`n_readings=0`, `missing_rate=1.0`, `stale=True`, `warnings=["No data..."]`). |
| `quality_check.py` (`check_quality`) | `if n >= 3:` inter-reading interval guard | Fewer than 3 readings | Bypasses coefficient of variation calculation; assigns default penalty `irregularity_score = 0.8`. |
| `quality_check.py` (`check_quality`) | `if time_diff <= 48:` matching guard | Manual and device readings exist | Computes divergence against nearest prior reading within 48h; guards against divide-by-zero via `max(abs(last_device["value"]), 1)`. |
| `quality_check.py` (`check_quality`) | `if n >= 5:` jump analysis guard | Fewer than 5 readings in series | Bypasses jump anomaly detection; prevents false step-change alarms on sparse data. |
| `reliability_scorer.py` (`score_reliability`) | `if quality.n_readings < 3:` | Sample size < 3 | Caps reliability score at 40.0; appends warning to rationale. |
| `reliability_scorer.py` (`score_reliability`) | `if quality.stale:` | Data older than 72 hours | Caps reliability score at 55.0; appends stale warning to rationale. |
| `reliability_scorer.py` (`score_reliability`) | Safety capping rules | `bad_quality_rate > 0.25`, `source_conflict`, `missing_rate > 0.35`, `sensor_anomaly` | Hard score caps (50.0–60.0) applied to override linear weights and prevent false high scores. |
| `trend_detection.py` (`detect_trend`) | `if subset.empty:` | No data for patient/metric | Returns `TrendResult` with `direction="insufficient_data"`, `slope=0.0`, `p_value=1.0`, `concerning=False`. |
| `trend_detection.py` (`detect_trend`) | `if n < cfg.min_points:` | Fewer than 5 observations in window | Returns `TrendResult` with `direction="insufficient_data"`, `slope=0.0`, `p_value=1.0`, `concerning=False`. |
| `uncertainty.py` (`quantify_uncertainty`) | Sample size & p-value penalization | `n_points < 5`, `p_value >= 0.05` | Confidence scaled down by multiplicative factors (0.5×, 0.6×, 0.85×) and capped at `reliability.score`. |
| `harm_assessment.py` (`assess_harm`) | `if items:` check | Harm penalties present | Generates structured mitigation: `"Do not schedule clinic visit... Request 3 consecutive daily device readings"`. |
| `decision.py` (`make_decision`) | Priority threshold check | `reliability.score < caution_min` (50) | Unconditional safe fallback: `outcome = SAFE_FALLBACK`, `alert = False`, provides 4 explicit recovery actions. |
| `orchestrator.py` (`run_pipeline`) | `len(tasks) > max_n` check | Tasks exceed capacity limit (50) | Truncates tasks to 50, sets `result.truncated = True`, appends warning to `result.warnings`. |
| `orchestrator.py` (`run_pipeline`) | `try ... except Exception as exc:` | Unexpected runtime failure in `assess_patient` | Catches per-patient exception, appends failure description to `result.warnings`, continues batch execution. |
| `timestamps.py` (`parse_timestamps`) | `pd.to_datetime(..., errors="coerce")` | Malformed timestamp series | Returns coerced datetime Series and emits warning with count of unparseable entries. |
| `timestamps.py` (`compute_interval_hours`)| `if len(timestamps) < 2:` | Fewer than 2 timestamps | Returns empty `pd.Series(dtype=float)` without computing `.diff()`. |
| `thresholds.py` (`band_for_value`) | `if value is None or value != value:` | `None` or `NaN` parameter value | Returns `None` cleanly, allowing risk scorer to handle missing parameter gracefully. |
| `risk_scorer.py` (`_recent_median`) | `if subset.empty:` or window empty | No readings within 7-day lookback | Falls back to last 3 readings; if still empty or all bad-quality, returns `None`. |
| `risk_scorer.py` (`_weekly_weight_gain`) | `if len(subset) < 2:` or `days < 6:` | Fewer than 2 weigh-ins or span < 6 days | Returns `None` to prevent annualized extrapolation over short noise bursts. |
| `risk_scorer.py` (`score_risk`) | Missing biometric handling | Any biometric is `None` | Logs `"Parameter missing"`, appends to contributions and rationale without halting execution. |
| `risk_scorer.py` (`score_risk`) | `if reliability.score < 50:` | Compromised systolic reliability (<50) | Hard safety gate: overrides predicted risk to `"indeterminate"`, sets `alert = False`. |
| `risk_scorer.py` (`score_risk`) | Step-down safety rule | Reliability in `[50, 70)` and predicted `"high"` | Steps down high risk to `"medium"` unless acute severe-range BP (SBP >= 160 or DBP >= 110) is confirmed. |
| `benchmarks.py` (`process_cpu_seconds`)| Multi-level `try ... except Exception:` | Platform-specific CPU API failure | Tries Windows `kernel32.GetProcessTimes`, then Unix `resource.getrusage`, then falls back to `time.process_time()`. |
| `benchmarks.py` (`process_rss_mb`) | Multi-level `try ... except Exception:` | Platform-specific memory API failure | Tries Unix `getrusage`, then Windows `psapi.GetProcessMemoryInfo`, returns `None` if unavailable. |
| `metrics.py` (`confusion`) | `if t not in index or p not in index:` | Unrecognized class labels | Skips unindexed label gracefully without IndexError. |
| `metrics.py` (`_prf`) | Zero-division protection | `tp + fp == 0` or `tp + fn == 0` | Returns `0.0` for precision, recall, or F1 without throwing `ZeroDivisionError`. |
| `dashboard/app.py` (`main`) | `try ... except FileNotFoundError:` | Dataset CSV files not yet generated | Displays clear error alert in Streamlit UI: `"Dataset not found. Run python scripts/generate_data.py first."` and calls `st.stop()`. |

---

## 5. Explicit System Limitations and Unhandled Edge Cases

The following operational and input conditions are **not** handled by internal guards and represent known limitations of the current codebase:

1. **Direct `validate_dataframe` Invocation with Missing Required Columns**:
   - Calling `validate_dataframe(df)` when required columns (`patient_id`, `timestamp`, `metric`, `value`, `source`) are absent raises an unhandled `ValueError`.
   - While `orchestrator.run_pipeline` catches all exceptions during batch execution, direct library calls to `assess_patient(df, ...)` or `validate_dataframe(df)` do not wrap this check and will propagate `ValueError` to the caller.

2. **Non-Linear Trend Trajectories**:
   - `detect_trend` uses simple linear regression (`scipy.stats.linregress`). Non-linear physiological trends (e.g., exponential deterioration, sinusoidal circadian rhythms, or sudden acute spikes after steady plateaus) are evaluated against a straight line fit.

3. **Slow Sensor Drift**:
   - The step-change detector only flags consecutive point jumps exceeding 20% whose magnitude is isolated relative to prior jumps. Slow, gradual drift caused by sensor calibration decay over weeks is indistinguishable from gradual physiological change.

4. **In-Memory and Synchronous Execution**:
   - The system does not maintain an external ACID database or asynchronous worker queue. All dataset ingestion, processing, and Streamlit dashboard interactions execute synchronously in-memory against local CSV files.

---

## 6. Test Execution Instructions

### Running the Entire Test Suite
Activate the project virtual environment and invoke pytest:
```bash
# Windows
.\.venv\Scripts\python.exe -m pytest tests/ -v

# Linux / macOS
pytest tests/ -v
```

### Running Individual Test Modules
```bash
# Unit & Quality Checks
pytest tests/test_quality_check.py -v

# Reliability Scorer
pytest tests/test_reliability_scorer.py -v

# Integration Pipeline
pytest tests/test_pipeline_integration.py -v

# Edge Cases & Fault Tolerance
pytest tests/test_edge_cases.py -v

# Review 2 Multi-Parameter Risk & Telemetry
pytest tests/test_review2.py -v
```

### Running Test Coverage
```bash
pytest --cov=src/maternal_reliability tests/ -v
```
