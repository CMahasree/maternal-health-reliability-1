"""Timestamp parsing and interval utilities."""

from __future__ import annotations

import pandas as pd


def parse_timestamps(series: pd.Series) -> tuple[pd.Series, list[str]]:
    """
    Parse timestamps with error handling for malformed values.

    Returns parsed series and warnings.
    """
    warnings: list[str] = []
    parsed = pd.to_datetime(series, utc=True, errors="coerce")
    bad = parsed.isna() & series.notna()
    if bad.any():
        warnings.append(f"{int(bad.sum())} malformed timestamp(s) could not be parsed")
    return parsed, warnings


def compute_interval_hours(timestamps: pd.Series) -> pd.Series:
    """Compute hours between consecutive timestamps."""
    if len(timestamps) < 2:
        return pd.Series(dtype=float)
    deltas = timestamps.diff().dt.total_seconds() / 3600.0
    return deltas
