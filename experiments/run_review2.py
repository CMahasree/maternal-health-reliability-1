"""Review 2 stress-test runner. Leaves experiments/run_experiments.py unchanged."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from maternal_reliability.review2.evaluate import (
    build_side_by_side_comparison,
    evaluate_review2,
    review1_baseline_snapshot,
)
from maternal_reliability.review2.thresholds import (
    BLOOD_GLUCOSE_MGDL,
    DIASTOLIC_BP_MMHG,
    HEART_RATE_BPM,
    HRV_RMSSD_MS,
    PARAMETER_REFERENCES,
    RISK_ACTIONS,
    SYSTOLIC_BP_MMHG,
    WEIGHT_GAIN_KG_PER_WEEK,
)


def _bands_table(name: str, unit: str, bands) -> list[dict]:
    rows = []
    for b in bands:
        lo = "−∞" if b.low is None else b.low
        hi = "+∞" if b.high is None else b.high
        rows.append(
            {
                "parameter": name,
                "unit": unit,
                "risk": b.name,
                "range": f"[{lo}, {hi})",
                "action": b.action,
            }
        )
    return rows


def save_plots(result: dict, out_dir: Path) -> None:
    cats = sorted(result["by_category"].keys())
    acc = [result["by_category"][c]["accuracy"] * 100 for c in cats]
    rec = [result["by_category"][c]["high_risk_recall"] * 100 for c in cats]
    prec = [result["by_category"][c]["high_risk_precision"] * 100 for c in cats]

    fig, ax = plt.subplots(figsize=(10, 4.5))
    x = range(len(cats))
    w = 0.25
    ax.bar([i - w for i in x], acc, width=w, label="Accuracy (3-class)")
    ax.bar(list(x), prec, width=w, label="High-risk precision")
    ax.bar([i + w for i in x], rec, width=w, label="High-risk recall")
    ax.set_xticks(list(x))
    ax.set_xticklabels(cats, rotation=20, ha="right")
    ax.set_ylabel("Percent")
    ax.set_title("Review 2 classification metrics by cohort category")
    ax.set_ylim(0, 105)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "metrics_by_category.png", dpi=140)
    plt.close(fig)

    cm = result["overall"]["confusion_clinical"]
    labels = cm["labels"]
    matrix = cm["matrix"]
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    im = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted risk")
    ax.set_ylabel("True clinical risk")
    ax.set_title("Review 2 confusion matrix (clinical labels vs prediction)")
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, str(matrix[i][j]), ha="center", va="center")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(out_dir / "confusion_clinical.png", dpi=140)
    plt.close(fig)

    bench = result["device_benchmarks"]
    conn = result["connectivity"]
    online = conn["online_baseline"]
    intermittent = conn["intermittent"]
    offline = conn["offline"]
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.bar(
        [
            "Mean score\nlatency",
            "p95 score\nlatency",
            "Online\nbaseline",
            "Intermittent\nslice",
            "Offline\nslice",
        ],
        [
            bench["mean_latency_ms"],
            bench["p95_latency_ms"],
            online["ms_per_patient"],
            intermittent["ms_per_patient"],
            offline["ms_per_patient"],
        ],
    )
    ax.set_ylabel("Milliseconds per patient")
    ax.set_title("Scoring latency vs separate connectivity slices (laptop proxy)")
    fig.tight_layout()
    fig.savefig(out_dir / "latency_vs_connectivity.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.bar(
        [
            "Online vs\nfull mixed",
            "Intermittent vs\nonline baseline",
            "Offline vs\nonline baseline",
        ],
        [
            online["vs_full_mixed"]["label_change_rate"] * 100,
            intermittent["vs_online_baseline"]["label_change_rate"] * 100,
            offline["vs_online_baseline"]["label_change_rate"] * 100,
        ],
    )
    ax.set_ylabel("Label change rate (%)")
    ax.set_title("Connectivity impact (three scenarios, not combined)")
    ax.set_ylim(0, 105)
    fig.tight_layout()
    fig.savefig(out_dir / "connectivity_impact.png", dpi=140)
    plt.close(fig)


def _md_cell(value) -> str:
    if value is None:
        return "not measured"
    return str(value)


def write_markdown(review1: dict, review2: dict, comparison: dict, out_path: Path) -> None:
    o = review2["overall"]
    sc = o["scores_clinical"]
    n2 = o["n_profiles"]
    lines = [
        "# Review 2 Evaluation Report",
        "",
        "Generated from `python experiments/run_review2.py`. Review 1 code and the original 8-profile experiment path were not replaced.",
        "",
        "## Scope (1–2 people, weeks not months)",
        "",
        "| In Review 2 | Deferred |",
        "|-------------|----------|",
        f"| {n2} simulated profiles, multi-parameter scoring, subgroup metrics | Prospective de-identified clinic data |",
        "| Documented clinical threshold bands | Diagnostic OGTT / BMI-specific weight charts |",
        "| Laptop proxy latency, tracemalloc RAM, measured process CPU, source size | Hardware farm / Android SoC traces |",
        "| Separate online / intermittent / offline scoring slices | Packet-level WAN emulator |",
        "",
        "## Who this is for",
        "",
        "- **Clinical partners:** high-risk recall, confusion matrix, when the system refuses to act (indeterminate).",
        "- **Engineering:** latency, CPU, local/offline scoring, reliability gate.",
        "- **Board / investors:** Review 1 8-profile headline is **not** the Review 2 claim; this round shows where performance drops.",
        "",
        "## Review 1 (original 8 profiles, re-measured)",
        "",
        f"- n = {review1['n_profiles']}",
        f"- Task = `{review1['metric']}`",
        f"- Accuracy = **{review1['accuracy']*100:.1f}%** (TP={review1['true_positives']}, FP={review1['false_positives']}, FN={review1['false_negatives']}, TN={review1['true_negatives']})",
        f"- Precision = {review1['precision']}, recall = {review1['recall']}, F1 = {review1.get('f1')}",
        f"- {review1['note']}",
        "",
        f"## Review 2 headline ({n2} profiles)",
        "",
        f"- Clinical 3-class accuracy = **{o['accuracy_clinical_3class']*100:.1f}%** (indeterminate counts as a miss against low/medium/high)",
        f"- Macro-F1 (low/medium/high) = **{o['macro_f1_clinical']:.3f}**",
        f"- Safety-aware accuracy (corner cases labeled indeterminate) = **{o['accuracy_safety_aware']*100:.1f}%**",
        f"- High-risk precision = {sc['high']['precision']}, high-risk recall = {sc['high']['recall']}, high-risk F1 = {sc['high']['f1']}",
        f"- Readings scored = {review2['n_readings']}; wall clock = {o['scoring_wall_clock_s']}s",
        "",
        "### Per-class (clinical ground truth)",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|-------|-----------|--------|----|---------|",
    ]
    for lab in ("low", "medium", "high"):
        s = sc[lab]
        lines.append(
            f"| {lab} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} | {s['support']} |"
        )
    lines += [
        "",
        "### Confusion matrix (rows = true clinical risk, columns = predicted)",
        "",
        "Labels: " + ", ".join(o["confusion_clinical"]["labels"]),
        "",
        "```",
        json.dumps(o["confusion_clinical"]["matrix"]),
        "```",
        "",
        "### Metrics by category",
        "",
        "| Category | n | Accuracy | Macro-F1 | High-risk recall | High-risk precision |",
        "|----------|---|----------|----------|------------------|---------------------|",
    ]
    for cat, m in sorted(review2["by_category"].items()):
        lines.append(
            f"| {cat} | {m['n']} | {m['accuracy']:.3f} | {m['macro_f1']:.3f} | {m['high_risk_recall']:.3f} | {m['high_risk_precision']:.3f} |"
        )
    b = review2["device_benchmarks"]
    c = review2["connectivity"]
    online = c["online_baseline"]
    intermittent = c["intermittent"]
    offline = c["offline"]
    counts = c["n_readings_by_status"]
    lines += [
        "",
        "## Device / connectivity (laptop proxy)",
        "",
        f"- Mean / p50 / p95 / max latency: {b['mean_latency_ms']} / {b['p50_latency_ms']} / {b['p95_latency_ms']} / {b['max_latency_ms']} ms",
        f"- Peak traced RAM: {b['peak_traced_ram_mb']} MB; process RSS: {b.get('process_rss_mb')} MB",
        f"- CPU: {b['cpu_time_s']} s process time; {b['cpu_percent']}% of one logical CPU during the timed loop ({b['logical_cpus']} logical CPUs). {b['cpu_metric']}",
        f"- Package source size: {b['package_source_kb']} KB",
        f"- Offline capable: {c['offline_capable']} — {c['note']}",
        f"- Readings by connectivity tag: online={counts.get('online', 0)}, intermittent={counts.get('intermittent', 0)}, offline={counts.get('offline', 0)}",
        "",
        "### Connectivity scenarios (measured separately)",
        "",
        "| Scenario | n readings | Batch s | ms/patient | Label change vs full mixed | Label change vs online baseline | Indeterminate |",
        "|----------|------------|---------|------------|----------------------------|---------------------------------|---------------|",
        (
            f"| online baseline | {online['n_readings']} | {online['batch_seconds']} | "
            f"{online['ms_per_patient']} | {online['vs_full_mixed']['label_change_rate']} "
            f"({online['vs_full_mixed']['label_changes']} patients) | — | "
            f"{online['vs_full_mixed']['indeterminate_count']} |"
        ),
        (
            f"| intermittent | {intermittent['n_readings']} | {intermittent['batch_seconds']} | "
            f"{intermittent['ms_per_patient']} | {intermittent['vs_full_mixed']['label_change_rate']} "
            f"({intermittent['vs_full_mixed']['label_changes']} patients) | "
            f"{intermittent['vs_online_baseline']['label_change_rate']} "
            f"({intermittent['vs_online_baseline']['label_changes']} patients) | "
            f"{intermittent['vs_full_mixed']['indeterminate_count']} |"
        ),
        (
            f"| offline | {offline['n_readings']} | {offline['batch_seconds']} | "
            f"{offline['ms_per_patient']} | {offline['vs_full_mixed']['label_change_rate']} "
            f"({offline['vs_full_mixed']['label_changes']} patients) | "
            f"{offline['vs_online_baseline']['label_change_rate']} "
            f"({offline['vs_online_baseline']['label_changes']} patients) | "
            f"{offline['vs_full_mixed']['indeterminate_count']} |"
        ),
        "",
        "**Stakeholder tradeoff:** For this product and timeline, **offline scoring + high-risk recall** matter more than squeezing CPU. CPU is measured (process time / wall time) so the cost is visible; the scorer is still rule-based and RAM/model-size are not the binding constraint. Intermittent and offline slices are reported separately because they are different failure modes.",
        "",
        "## Review 1 vs Review 2 (measured only)",
        "",
        f"- Review 1 task: `{comparison['tasks']['review1']}`",
        f"- Review 2 task: {comparison['tasks']['review2']}",
        "",
        "| Metric | Review 1 | Review 2 | Directly comparable | Note |",
        "|--------|----------|----------|---------------------|------|",
    ]
    for row in comparison["rows"]:
        comparable = "yes" if row["directly_comparable"] else "no"
        lines.append(
            f"| {row['metric']} | {_md_cell(row['review1'])} | {_md_cell(row['review2'])} | {comparable} | {row['note']} |"
        )
    lines += [
        "",
        "## Why Review 2 differs from Review 1",
        "",
        f"Review 1 tested alert-on-reliable-systolic-trend on 8 hand-built stories. Review 2 tests 3-class (plus indeterminate) risk on {n2} profiles including missing, noisy, conflicting, reduced fetal movement, and fever data, using SBP, DBP, glucose, HR, HRV, weight gain, fetal movement, temperature, and SpO2. Accuracy is expected to fall; that is the result, not a failure of the experiment.",
        "",
        "Figures: `metrics_by_category.png`, `confusion_clinical.png`, `latency_vs_connectivity.png`, `connectivity_impact.png`.",
        "",
        "## Threshold references",
        "",
    ]
    for k, v in PARAMETER_REFERENCES.items():
        lines.append(f"- **{k}:** {v}")
    for k, v in RISK_ACTIONS.items():
        lines.append(f"- **Action [{k}]:** {v}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_thresholds_doc(path: Path) -> None:
    rows = []
    rows += _bands_table("systolic_bp", "mmHg", SYSTOLIC_BP_MMHG)
    rows += _bands_table("diastolic_bp", "mmHg", DIASTOLIC_BP_MMHG)
    rows += _bands_table("blood_glucose_mgdl", "mg/dL", BLOOD_GLUCOSE_MGDL)
    rows += _bands_table("heart_rate", "bpm", HEART_RATE_BPM)
    rows += _bands_table("hrv_rmssd_ms", "ms", HRV_RMSSD_MS)
    rows += _bands_table("weight_gain", "kg/week", WEIGHT_GAIN_KG_PER_WEEK)
    lines = [
        "# Review 2 biometric thresholds",
        "",
        "Screening bands for remote monitoring — not a diagnosis.",
        "",
        "| Parameter | Unit | Risk | Range | Action |",
        "|-----------|------|------|-------|--------|",
    ]
    for r in rows:
        lines.append(f"| {r['parameter']} | {r['unit']} | {r['risk']} | {r['range']} | {r['action']} |")
    lines += ["", "## References"]
    for k, v in PARAMETER_REFERENCES.items():
        lines.append(f"- {k}: {v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    out_dir = ROOT / "experiments" / "results" / "review2"
    out_dir.mkdir(parents=True, exist_ok=True)
    docs = ROOT / "docs"

    review1 = review1_baseline_snapshot(seed=42)
    review2 = evaluate_review2(seed=2026)
    comparison = build_side_by_side_comparison(review1, review2)

    serializable = dict(review2)
    serializable["rows"] = review2["rows"]
    serializable["comparison"] = comparison
    with open(out_dir / "review2_metrics.json", "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, default=str)
    with open(out_dir / "review1_snapshot.json", "w", encoding="utf-8") as f:
        json.dump(review1, f, indent=2)
    with open(out_dir / "review1_vs_review2.json", "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)
    pd.DataFrame(review2["rows"]).to_csv(out_dir / "review2_predictions.csv", index=False)

    save_plots(review2, out_dir)
    write_markdown(review1, review2, comparison, docs / "REVIEW2_REPORT.md")
    write_thresholds_doc(docs / "REVIEW2_THRESHOLDS.md")

    o = review2["overall"]
    print("Review 1 (8 profiles) accuracy:", review1["accuracy"])
    print("Review 2 n=", o["n_profiles"], "clinical accuracy=", o["accuracy_clinical_3class"])
    print("High-risk P/R/F1:", o["scores_clinical"]["high"])
    print("Saved", out_dir)


if __name__ == "__main__":
    main()
