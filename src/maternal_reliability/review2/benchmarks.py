"""Edge-device style benchmarks for the Review 2 scorer (laptop proxy)."""

from __future__ import annotations

import os
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from maternal_reliability.review2.risk_scorer import score_risk


def _src_bytes() -> int:
    root = Path(__file__).resolve().parents[1]
    total = 0
    for path in root.rglob("*.py"):
        total += path.stat().st_size
    return total


def process_cpu_seconds() -> float:
    """Process CPU time (user + kernel) in seconds — measured, not estimated."""
    # Strategy 1 (Windows): Query kernel32.GetProcessTimes to capture exact user and kernel CPU ticks
    try:
        import ctypes
        import ctypes.wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [
                ("dwLowDateTime", ctypes.wintypes.DWORD),
                ("dwHighDateTime", ctypes.wintypes.DWORD),
            ]

        def _filetime_seconds(ft: FILETIME) -> float:
            ticks = (ft.dwHighDateTime << 32) | ft.dwLowDateTime
            return ticks / 10_000_000.0

        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
        k32.GetProcessTimes.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
            ctypes.POINTER(FILETIME),
        ]
        k32.GetProcessTimes.restype = ctypes.wintypes.BOOL

        creation = FILETIME()
        exit_time = FILETIME()
        kernel = FILETIME()
        user = FILETIME()
        handle = k32.GetCurrentProcess()
        if k32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return _filetime_seconds(kernel) + _filetime_seconds(user)
    except Exception:
        pass
    # Strategy 2 (POSIX / Linux / macOS): Query resource.getrusage for user + system CPU time
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        return float(usage.ru_utime + usage.ru_stime)
    except Exception:
        pass
    # Strategy 3 (Fallback): Python standard library process_time
    return time.process_time()


def _cpu_stats(cpu_s: float, wall_s: float) -> dict:
    n_logical = os.cpu_count() or 1
    util_one_core = (100.0 * cpu_s / wall_s) if wall_s > 0 else 0.0
    return {
        "cpu_time_s": round(cpu_s, 4),
        "cpu_percent": round(util_one_core, 2),
        "cpu_percent_of_logical_cpus": round(util_one_core / n_logical, 2),
        "logical_cpus": n_logical,
        "cpu_metric": (
            "Process CPU seconds (Windows GetProcessTimes user+kernel, or Unix rusage, "
            "else time.process_time) divided by wall clock. cpu_percent is utilization of "
            "one logical CPU during the timed window."
        ),
    }


def _score_all(readings: pd.DataFrame, patient_ids: list[str]) -> tuple[dict, float, float]:
    cpu0 = process_cpu_seconds()
    t0 = time.perf_counter()
    scores = {pid: score_risk(readings, pid) for pid in patient_ids}
    wall_s = time.perf_counter() - t0
    cpu_s = process_cpu_seconds() - cpu0
    return scores, wall_s, cpu_s


def _label_delta(reference: dict, other: dict, patient_ids: list[str], other_key: str) -> dict:
    n = len(patient_ids)
    changed = 0
    indeterminate = 0
    pairs = []
    for pid in patient_ids:
        ref_lab = reference[pid].predicted_risk
        oth_lab = other[pid].predicted_risk
        if oth_lab == "indeterminate":
            indeterminate += 1
        if ref_lab != oth_lab:
            changed += 1
            if len(pairs) < 12:
                pairs.append(
                    {
                        "patient_id": pid,
                        "full_mixed": ref_lab,
                        other_key: oth_lab,
                    }
                )
    return {
        "label_changes": changed,
        "label_change_rate": round(changed / n, 4) if n else 0.0,
        "indeterminate_count": indeterminate,
        "example_changes": pairs,
    }


def _slice_report(
    name: str,
    description: str,
    slice_df: pd.DataFrame,
    patient_ids: list[str],
    full_scores: dict,
    online_scores: dict | None,
) -> dict:
    scores, wall_s, cpu_s = _score_all(slice_df, patient_ids)
    vs_full = _label_delta(full_scores, scores, patient_ids, name)
    report = {
        "name": name,
        "description": description,
        "n_readings": int(len(slice_df)),
        "batch_seconds": round(wall_s, 4),
        "ms_per_patient": round(1000.0 * wall_s / max(len(patient_ids), 1), 3),
        **_cpu_stats(cpu_s, wall_s),
        "vs_full_mixed": vs_full,
    }
    if online_scores is not None:
        report["vs_online_baseline"] = _label_delta(online_scores, scores, patient_ids, name)
    return report


def benchmark_callable(
    fn: Callable[[str], object],
    patient_ids: list[str],
    repeats: int = 1,
) -> dict:
    """Latency / RAM / CPU for any per-patient callable (Review 1 harness uses this)."""
    if patient_ids:
        fn(patient_ids[0])

    latencies_ms: list[float] = []
    tracemalloc.start()
    cpu0 = process_cpu_seconds()
    t0 = time.perf_counter()
    for _ in range(repeats):
        for pid in patient_ids:
            start = time.perf_counter()
            fn(pid)
            latencies_ms.append((time.perf_counter() - start) * 1000.0)
    elapsed = time.perf_counter() - t0
    cpu_s = process_cpu_seconds() - cpu0
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    latencies_ms.sort()
    n = len(latencies_ms)
    p50 = latencies_ms[n // 2] if n else 0.0
    p95 = latencies_ms[int(n * 0.95)] if n else 0.0
    out = {
        "n_scores": n,
        "wall_clock_s": round(elapsed, 4),
        "mean_latency_ms": round(sum(latencies_ms) / n, 3) if n else 0.0,
        "p50_latency_ms": round(p50, 3),
        "p95_latency_ms": round(p95, 3),
        "max_latency_ms": round(latencies_ms[-1], 3) if n else 0.0,
        "peak_traced_ram_mb": round(peak / (1024 * 1024), 3),
        "end_traced_ram_mb": round(current / (1024 * 1024), 3),
        "package_source_bytes": _src_bytes(),
        "package_source_kb": round(_src_bytes() / 1024, 1),
        **_cpu_stats(cpu_s, elapsed),
        "process_rss_mb": process_rss_mb(),
        "note": (
            "Rule-based scorer; 'model size' is Python package source, not a trained weight file. "
            "RAM is tracemalloc peak in-process (RSS reported separately). "
            "Laptop is a proxy for clinic PC / rugged tablet."
        ),
    }
    return out


def benchmark_scoring(readings: pd.DataFrame, patient_ids: list[str], repeats: int = 1) -> dict:
    """Measure latency, peak traced memory, and CPU for sequential Review 2 scoring."""
    return benchmark_callable(lambda pid: score_risk(readings, pid), patient_ids, repeats=repeats)


def connectivity_impact(readings: pd.DataFrame, patient_ids: list[str]) -> dict:
    """Evaluate online, intermittent, and offline connectivity separately (not combined)."""
    # 1. Tally raw volume of readings across network states
    status_counts = {
        str(k): int(v) for k, v in readings["connectivity_status"].value_counts().to_dict().items()
    }
    for key in ("online", "intermittent", "offline"):
        status_counts.setdefault(key, 0)

    # 2. Partition dataset into mutually exclusive connectivity slices for ablation
    online = readings[readings["connectivity_status"] == "online"].copy()
    intermittent = readings[readings["connectivity_status"] == "intermittent"].copy()
    offline = readings[readings["connectivity_status"] == "offline"].copy()

    # 3. Score the full mixed dataset (on-device store) vs purely online sync stream
    full_scores, time_all, cpu_all = _score_all(readings, patient_ids)
    online_scores, time_online, cpu_online = _score_all(online, patient_ids)

    # Compare label stability between full store and online baseline
    online_vs_full = _label_delta(full_scores, online_scores, patient_ids, "online_baseline")
    online_report = {
        "name": "online_baseline",
        "description": (
            "Score using only readings tagged connectivity_status=online "
            "(successful live sync). This is the online baseline."
        ),
        "n_readings": int(len(online)),
        "batch_seconds": round(time_online, 4),
        "ms_per_patient": round(1000.0 * time_online / max(len(patient_ids), 1), 3),
        **_cpu_stats(cpu_online, time_online),
        "vs_full_mixed": online_vs_full,
    }

    intermittent_report = _slice_report(
        "intermittent",
        (
            "Score using only readings tagged connectivity_status=intermittent "
            "(flaky-link deliveries). Offline rows are not included."
        ),
        intermittent,
        patient_ids,
        full_scores,
        online_scores,
    )
    offline_report = _slice_report(
        "offline",
        (
            "Score using only readings tagged connectivity_status=offline "
            "(device-local / delayed cache). Intermittent rows are not included."
        ),
        offline,
        patient_ids,
        full_scores,
        online_scores,
    )

    indeterminate_full = sum(
        1 for pid in patient_ids if full_scores[pid].predicted_risk == "indeterminate"
    )

    return {
        "n_patients": len(patient_ids),
        "n_readings_by_status": status_counts,
        "offline_capable": True,
        "full_mixed": {
            "description": "All stored readings regardless of connectivity tag (on-device store).",
            "n_readings": int(len(readings)),
            "batch_seconds": round(time_all, 4),
            "ms_per_patient": round(1000.0 * time_all / max(len(patient_ids), 1), 3),
            **_cpu_stats(cpu_all, time_all),
            "indeterminate_count": indeterminate_full,
        },
        "online_baseline": online_report,
        "intermittent": intermittent_report,
        "offline": offline_report,
        "note": (
            "Scoring is fully local (no network call). Online, intermittent, and offline "
            "are scored as three separate data slices. Intermittent and offline are never "
            "merged into one ablation."
        ),
        # Keys kept so older report snippets that read batch times still resolve.
        "batch_seconds_all_readings": round(time_all, 4),
        "batch_seconds_online_only": round(time_online, 4),
    }


def process_rss_mb() -> float | None:
    try:
        import resource  # Unix

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        pass
    try:
        import ctypes
        import ctypes.wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.wintypes.DWORD),
                ("PageFaultCount", ctypes.wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
            ctypes.wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = ctypes.wintypes.BOOL
        handle = k32.GetCurrentProcess()
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return round(counters.WorkingSetSize / (1024 * 1024), 2)
        return None
    except Exception:
        return None
