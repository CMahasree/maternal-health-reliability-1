# Data Schema

## Device Readings (`simulated_readings.csv`)

| Column | Type | Description |
|--------|------|-------------|
| `reading_id` | string | Unique identifier for audit trail |
| `patient_id` | string | Patient identifier (e.g., P001) |
| `timestamp` | datetime (UTC) | Measurement time; may have jitter ±6–12h |
| `metric` | string | `systolic_bp`, `diastolic_bp`, `heart_rate`, `weight_kg`, `fetal_movement` |
| `value` | float | Measured value in clinical units |
| `source` | string | `device`, `manual`, or `health_worker` |
| `device_id` | string | Assigned monitoring device |
| `connectivity_status` | string | `online`, `offline`, or `intermittent` |
| `quality_label` | string | `good`, `suspect`, `bad`, or `missing_imputed` |
| `gap_before_hours` | float | Hours since previous reading for same metric |
| `is_gap` | bool | True if gap exceeds 2× expected interval |
| `notes` | string | Free-text annotation |
| `scenario` | string | Simulation scenario label (metadata) |

## Ground Truth Labels (`ground_truth_labels.csv`)

| Column | Type | Description |
|--------|------|-------------|
| `patient_id` | string | Patient identifier |
| `scenario` | string | Simulation scenario |
| `ground_truth_reliable` | bool | Whether data is truly reliable for trend analysis |
| `ground_truth_alert` | bool | Whether a clinical alert is truly warranted |

## How Gaps Are Represented

1. **Missing rows**: During multi-week outages, no readings are generated for affected days.
2. **`gap_before_hours`**: Computed at generation time as hours since the prior reading for the same patient-metric pair.
3. **`is_gap`**: Boolean flag when `gap_before_hours > 2 × EXPECTED_INTERVAL_HOURS`.
4. **`connectivity_status = offline`**: Readings during outage windows are omitted entirely; downstream quality check computes missing rate from expected vs actual point density.

## Expected Measurement Intervals

| Metric | Expected Interval |
|--------|-------------------|
| systolic_bp | 24 hours |
| diastolic_bp | 24 hours |
| heart_rate | 12 hours |
| weight_kg | 168 hours (weekly) |
| fetal_movement | 24 hours |

## Manual vs Device Entries

Manual entries share the same schema. Source conflicts are detected when a manual/health-worker reading within 48h differs by >10% from the nearest device reading.
