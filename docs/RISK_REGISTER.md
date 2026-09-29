# Risk Register

| ID | Failure Mode | Impact | Likelihood | Mitigation | System Behavior |
|----|-------------|--------|------------|------------|-----------------|
| R1 | Device offline >2 weeks | Missed or false trends | High | Missing rate scoring, gap detection, safe fallback | Score drops below 50; alert suppressed; re-check scheduled |
| R2 | Manual entry contradicts device | Wrong clinical action | Medium | Source conflict detection (10% threshold, 48h window) | Source agreement component drops to 30; caution/fallback |
| R3 | Sensor malfunction (sudden spikes) | False preeclampsia alert | Medium | Isolated step-change detection (>20% jump vs prior median); score cap at 55 | Malfunction series scored unreliable; trend suppressed |
| R4 | Irregular measurement timing | Unstable trend estimates | Medium | Regularity component (CV of intervals) | Irregularity score penalizes confidence |
| R5 | Stale data (patient stopped reporting) | Acting on outdated trend | Medium | 72h stale threshold caps score at 55 | Stale flag triggers caution with re-contact action |
| R6 | Batch overload (>50 patients) | Delayed assessments | Low | Capacity limit truncates with warning | Pipeline truncates at 50; dashboard shows warning |
| R7 | Malformed timestamps | Pipeline crash | Low | validate_dataframe drops bad rows with warning | Graceful degradation; warnings in output |
| R8 | False negative (miss real trend) | Delayed treatment | Medium | Lower threshold for caution (50–69) with re-check | Caution outcome with 24h confirmatory reading request |
| R9 | False positive (alert on bad data) | Unnecessary clinic visit | High | Multi-component reliability score + harm assessment | Harm score displayed; baseline comparison shows improvement |
| R10 | Health worker unavailable | No manual verification | Medium | Fallback lists device re-sync as alternative | Safe fallback actions include connectivity troubleshooting |

## Harm Prevention Summary

The system prevents harm by:
1. **Suppressing alerts** when reliability < 50 (R1, R2, R3)
2. **Requiring verification** at 50–69 reliability (R2, R8)
3. **Showing harm cost** before any action (R9)
4. **Documenting evidence** for supervisor audit (all risks)
