"""Classification metrics without sklearn (keeps Review 2 dependency-light)."""

from __future__ import annotations

from collections import defaultdict


LABELS = ["low", "medium", "high", "indeterminate"]


def confusion(y_true: list[str], y_pred: list[str], labels: list[str] | None = None) -> dict:
    labels = labels or LABELS
    index = {l: i for i, l in enumerate(labels)}
    matrix = [[0 for _ in labels] for _ in labels]
    for t, p in zip(y_true, y_pred):
        if t not in index or p not in index:
            continue
        matrix[index[t]][index[p]] += 1
    return {"labels": labels, "matrix": matrix}


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1


def per_class_scores(y_true: list[str], y_pred: list[str], labels: list[str] | None = None) -> dict:
    labels = labels or LABELS
    scores = {}
    for lab in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p != lab)
        prec, rec, f1 = _prf(tp, fp, fn)
        support = sum(1 for t in y_true if t == lab)
        scores[lab] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
    return scores


def accuracy(y_true: list[str], y_pred: list[str]) -> float:
    if not y_true:
        return 0.0
    return sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true)


def macro_f1(scores: dict) -> float:
    vals = [s["f1"] for s in scores.values() if s["support"] > 0]
    return sum(vals) / len(vals) if vals else 0.0


def weighted_f1(scores: dict) -> float:
    total = sum(s["support"] for s in scores.values())
    if not total:
        return 0.0
    return sum(s["f1"] * s["support"] for s in scores.values()) / total


def binary_high_risk(y_true: list[str], y_pred: list[str]) -> dict:
    yt = [t == "high" for t in y_true]
    yp = [p == "high" for p in y_pred]
    tp = sum(t and p for t, p in zip(yt, yp))
    fp = sum((not t) and p for t, p in zip(yt, yp))
    fn = sum(t and (not p) for t, p in zip(yt, yp))
    tn = sum((not t) and (not p) for t, p in zip(yt, yp))
    prec, rec, f1 = _prf(tp, fp, fn)
    n = len(y_true)
    return {
        "positive_class": "high",
        "accuracy": round((tp + tn) / n, 4) if n else 0.0,
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "support_positive": sum(yt),
    }


def f1_from_precision_recall(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def subgroup_metrics(rows: list[dict], key: str) -> dict[str, dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[str(row[key])].append(row)
    out = {}
    for name, items in buckets.items():
        yt = [r["y_true"] for r in items]
        yp = [r["y_pred"] for r in items]
        scores = per_class_scores(yt, yp)
        out[name] = {
            "n": len(items),
            "accuracy": round(accuracy(yt, yp), 4),
            "macro_f1": round(macro_f1(scores), 4),
            "high_risk_recall": scores.get("high", {}).get("recall", 0.0),
            "high_risk_precision": scores.get("high", {}).get("precision", 0.0),
            "scores": scores,
            "confusion": confusion(yt, yp),
        }
    return out
