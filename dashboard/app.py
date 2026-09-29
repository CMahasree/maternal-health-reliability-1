"""Streamlit dashboard for maternal health reliability scoring."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add src folder to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import pandas as pd
import streamlit as st

from maternal_reliability.baseline.simple_scorer import baseline_score
from maternal_reliability.config import OPERATIONAL_LIMITS, THRESHOLDS
from maternal_reliability.pipeline.orchestrator import (
    assess_patient,
    assessment_to_dict,
    run_pipeline,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    readings = pd.read_csv(DATA_DIR / "simulated_readings.csv", parse_dates=["timestamp"])
    labels = pd.read_csv(DATA_DIR / "ground_truth_labels.csv")
    return readings, labels


def main() -> None:
    st.set_page_config(
        page_title="Maternal Health Reliability Scorer",
        page_icon="🩺",
        layout="wide",
    )

    st.title("Maternal Health Data Reliability Scorer")
    st.markdown(
        "Assess trend reliability before clinical action. "
        "**Transparency over prediction** — every score shows its evidence."
    )

    try:
        readings, labels = load_data()
    except FileNotFoundError:
        st.error("Dataset not found. Run `python scripts/generate_data.py` first.")
        st.stop()

    patients = sorted(readings["patient_id"].unique())
    col1, col2, col3 = st.columns(3)
    with col1:
        patient_id = st.selectbox("Patient", patients)
    with col2:
        metric = st.selectbox("Metric", ["systolic_bp", "diastolic_bp", "heart_rate", "weight_kg"])
    with col3:
        st.metric("Recheck interval", f"{OPERATIONAL_LIMITS.recheck_interval_hours}h")

    assessment = assess_patient(readings, patient_id, metric)
    baseline = baseline_score(readings, patient_id, metric)
    gt = labels[labels["patient_id"] == patient_id].iloc[0] if len(labels) > 0 else None

    # Header metrics
    m1, m2, m3, m4 = st.columns(4)
    score = assessment.reliability.score
    m1.metric("Reliability Score", f"{score}/100", assessment.reliability.label.value)
    m2.metric("Confidence", f"{assessment.uncertainty.confidence}%")
    m3.metric("Harm if Acted Upon", assessment.harm.total_harm_score)
    m4.metric("Decision", assessment.decision.outcome.value.replace("_", " ").title())

    # Decision banner
    outcome = assessment.decision.outcome.value
    if outcome == "actionable":
        st.success(f"**{assessment.decision.message}**")
    elif outcome == "safe_fallback":
        st.error(f"**{assessment.decision.message}**")
    elif outcome == "caution":
        st.warning(f"**{assessment.decision.message}**")
    else:
        st.info(f"**{assessment.decision.message}**")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Trend & Data", "Evidence Chain", "Harm Assessment", "Baseline Comparison", "All Patients"]
    )

    with tab1:
        patient_data = readings[
            (readings["patient_id"] == patient_id) & (readings["metric"] == metric)
        ].sort_values("timestamp")
        st.subheader("Reading Timeline")
        st.line_chart(patient_data.set_index("timestamp")["value"])
        st.dataframe(
            patient_data[
                ["timestamp", "value", "source", "connectivity_status", "quality_label", "is_gap"]
            ],
            use_container_width=True,
        )
        st.subheader("Trend Analysis")
        t = assessment.trend
        st.write(
            f"Direction: **{t.direction}** | Slope: **{t.slope_per_day}**/day | "
            f"p-value: **{t.p_value}** | Concerning: **{t.concerning}** | Points: **{t.n_points}**"
        )

    with tab2:
        st.subheader("Score Breakdown")
        components = assessment.reliability.components
        st.bar_chart(pd.Series(components))
        st.subheader("Rationale")
        for r in assessment.reliability.rationale:
            st.write(f"- {r}")
        st.subheader("Contributing Data Points")
        if assessment.trend.evidence_points:
            st.dataframe(pd.DataFrame(assessment.trend.evidence_points), use_container_width=True)
        st.subheader("Full Evidence Summary")
        st.code(assessment.evidence.summary)

    with tab3:
        st.subheader("Potential Harm from Acting on Unreliable Trend")
        if assessment.harm.harm_items:
            st.dataframe(pd.DataFrame(assessment.harm.harm_items), use_container_width=True)
        else:
            st.write("No significant harm risk identified.")
        st.subheader("Safe Fallback Actions")
        for action in assessment.decision.fallback_actions:
            st.write(f"- {action}")

    with tab4:
        st.subheader("Baseline vs Enhanced Scorer")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Baseline (>20% missing = suppress)**")
            st.write(f"Alert: **{baseline.alert}**")
            st.write(baseline.reason)
        with c2:
            st.markdown("**Enhanced Reliability Scorer**")
            st.write(f"Alert: **{assessment.decision.alert}**")
            st.write(assessment.decision.message)
        if gt is not None:
            st.markdown("**Ground Truth (simulation)**")
            st.write(
                f"Reliable data: {gt['ground_truth_reliable']} | "
                f"True alert needed: {gt['ground_truth_alert']}"
            )

    with tab5:
        st.subheader("Batch Assessment Overview")
        pipeline = run_pipeline(readings)
        rows = [assessment_to_dict(a) for a in pipeline.assessments]
        overview = pd.DataFrame(rows)[
            ["patient_id", "reliability_score", "reliability_label", "trend_concerning",
             "confidence", "decision", "alert", "harm_score"]
        ]
        st.dataframe(overview, use_container_width=True)

        if pipeline.truncated:
            st.warning(f"Results truncated to {OPERATIONAL_LIMITS.max_pending_assessments} assessments.")

    with st.sidebar:
        st.header("Operational Limits")
        st.json({
            "max_pending_assessments": OPERATIONAL_LIMITS.max_pending_assessments,
            "recheck_interval_hours": OPERATIONAL_LIMITS.recheck_interval_hours,
            "stale_data_hours": OPERATIONAL_LIMITS.stale_data_hours,
        })
        st.header("Thresholds")
        st.json({
            "actionable_min": THRESHOLDS.actionable_min,
            "caution_min": THRESHOLDS.caution_min,
            "high_min": THRESHOLDS.high_min,
        })
        st.header("Export")
        export = assessment_to_dict(assessment)
        st.download_button(
            "Download Assessment JSON",
            json.dumps(export, indent=2, default=str),
            file_name=f"{patient_id}_{metric}_assessment.json",
        )


if __name__ == "__main__":
    main()
