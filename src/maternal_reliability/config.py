"""Configuration, thresholds, and operational limits for the reliability scorer."""

from dataclasses import dataclass
from enum import Enum


class ReliabilityLabel(str, Enum):
    """Reliability classification labels."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNRELIABLE = "unreliable"


class DecisionOutcome(str, Enum):
    """Clinical decision outcomes."""

    ACTIONABLE = "actionable"
    CAUTION = "caution"
    NOT_ACTIONABLE = "not_actionable"
    SAFE_FALLBACK = "safe_fallback"


@dataclass(frozen=True)
class ReliabilityThresholds:
    """
    Reliability score thresholds (0-100 scale).

    Reasoning:
    - >= 70 (HIGH/MODERATE boundary): Sufficient data density, temporal regularity,
      and source agreement to support clinical action in remote maternal monitoring.
    - 50-69 (MODERATE/LOW): Trend may exist but gaps or conflicts warrant verification
      before scheduling clinic visits or medication changes.
    - < 50 (LOW/UNRELIABLE): Too many gaps, conflicts, or sensor failures; safe fallback
      required to avoid false alarms and wasted follow-ups.
    """

    actionable_min: float = 70.0
    caution_min: float = 50.0
    high_min: float = 85.0

    # Component weights (must sum to 1.0)
    weight_completeness: float = 0.30
    weight_regularity: float = 0.20
    weight_source_agreement: float = 0.20
    weight_connectivity: float = 0.15
    weight_quality_flags: float = 0.15


@dataclass(frozen=True)
class TrendConfig:
    """Trend detection parameters."""

    min_points: int = 5
    concerning_slope_bp_per_day: float = 1.5  # systolic mmHg/day
    concerning_slope_dbp_per_day: float = 1.0  # diastolic mmHg/day
    concerning_slope_hr_per_day: float = 2.0  # bpm/day
    concerning_slope_glucose_per_day: float = 3.0  # mg/dL/day
    concerning_slope_weight_kg_per_day: float = 0.15  # ~1 kg/week
    window_days: int = 14
    significance_p_value: float = 0.05


@dataclass(frozen=True)
class OperationalLimits:
    """
    Capacity and scheduling constraints for care teams.

    Documented for deployment planning in resource-limited settings.
    """

    max_pending_assessments: int = 50
    recheck_interval_hours: int = 24
    max_assessments_per_patient_per_day: int = 4
    stale_data_hours: int = 72
    batch_processing_max_patients: int = 200


@dataclass(frozen=True)
class HarmCosts:
    """
    Estimated harm costs (relative units) for false clinical actions.

    Used to quantify downstream impact when unreliable trends are acted upon.
    Values derived from stakeholder assumptions (see docs/STAKEHOLDER_ASSUMPTIONS.md).
    """

    unnecessary_clinic_visit: float = 10.0
    delayed_real_action: float = 25.0
    unnecessary_medication_change: float = 15.0
    patient_anxiety: float = 5.0
    resource_waste_per_false_alert: float = 8.0


# Singleton defaults
THRESHOLDS = ReliabilityThresholds()
TREND_CONFIG = TrendConfig()
OPERATIONAL_LIMITS = OperationalLimits()
HARM_COSTS = HarmCosts()

# Baseline reference scorer threshold
BASELINE_MISSING_DATA_THRESHOLD = 0.20
