"""Latency and resource benchmarking for Review 3 evaluation.

Measures quantitative latency, throughput, memory, and CPU metrics on the expanded
200-profile cohort using real measurements.
"""

from __future__ import annotations

import os
import platform
import sys
import time
import tracemalloc
from typing import Any

import numpy as np
import pandas as pd

from maternal_reliability.pipeline.orchestrator import assess_patient
from maternal_reliability.review2.benchmarks import process_cpu_seconds, process_rss_mb


def benchmark_review3(
    readings: pd.DataFrame,
    patient_ids: list[str],
    metric: str = "systolic_bp",
    repeats: int = 1,
) -> dict[str, Any]:
    """
    Run latency and resource benchmarks on patient scoring.

    Measures:
    - per-patient latencies (mean, median, p95, max, min)
    - throughput (profiles/sec and readings/sec)
    - memory consumption (tracemalloc peak heap and process RSS)
    - process CPU seconds and core utilization
    """
    n_patients = len(patient_ids)
    n_readings = len(readings)

    # Start resource monitors
    tracemalloc.start()
    tracemalloc.reset_peak()
    rss_before = process_rss_mb()
    cpu_before = process_cpu_seconds()
    t_start = time.perf_counter()

    latencies_ms = []

    for _ in range(repeats):
        for pid in patient_ids:
            t0 = time.perf_counter()
            assess_patient(readings, pid, metric)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)

    t_end = time.perf_counter()
    cpu_after = process_cpu_seconds()
    rss_after = process_rss_mb()
    peak_bytes, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    wall_s = max(1e-6, t_end - t_start)
    cpu_s = max(0.0, cpu_after - cpu_before)
    logical_cpus = os.cpu_count() or 1
    cpu_percent = (100.0 * cpu_s / wall_s) if wall_s > 0 else 0.0

    mean_ms = float(np.mean(latencies_ms))
    median_ms = float(np.median(latencies_ms))
    p95_ms = float(np.percentile(latencies_ms, 95))
    max_ms = float(np.max(latencies_ms))
    min_ms = float(np.min(latencies_ms))

    profiles_per_sec = (n_patients * repeats) / wall_s
    readings_per_sec = (n_readings * repeats) / wall_s

    import scipy

    return {
        "execution": {
            "n_profiles": n_patients,
            "n_readings": n_readings,
            "repeats": repeats,
            "total_evaluations": len(latencies_ms),
            "total_wall_clock_s": round(wall_s, 4),
        },
        "latency_ms": {
            "mean": round(mean_ms, 3),
            "median": round(median_ms, 3),
            "p95": round(p95_ms, 3),
            "max": round(max_ms, 3),
            "min": round(min_ms, 3),
        },
        "throughput": {
            "profiles_per_second": round(profiles_per_sec, 2),
            "readings_per_second": round(readings_per_sec, 2),
        },
        "resources": {
            "peak_traced_ram_mb": round(peak_bytes / (1024 * 1024), 3),
            "process_rss_mb_before": round(rss_before, 2) if rss_before else None,
            "process_rss_mb_after": round(rss_after, 2) if rss_after else None,
            "process_cpu_seconds": round(cpu_s, 4),
            "cpu_utilization_single_core_pct": round(cpu_percent, 2),
            "cpu_utilization_all_cores_pct": round(cpu_percent / logical_cpus, 2),
            "logical_cpus": logical_cpus,
        },
        "environment": {
            "os": platform.platform(),
            "python_version": sys.version.split()[0],
            "pandas_version": pd.__version__,
            "scipy_version": scipy.__version__,
            "numpy_version": np.__version__,
            "disclaimer": (
                "Local/desktop benchmark results do not establish performance "
                "on constrained remote devices."
            ),
        },
    }
