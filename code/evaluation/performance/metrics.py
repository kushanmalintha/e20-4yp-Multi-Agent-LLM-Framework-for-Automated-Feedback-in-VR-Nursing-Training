from __future__ import annotations

from statistics import mean, median
from typing import Iterable


def percentile(values: Iterable[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]

    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize_latencies(values: Iterable[float]) -> dict[str, float]:
    values = list(values)
    if not values:
        return {
            "count": 0,
            "mean": 0.0,
            "p50": 0.0,
            "p95": 0.0,
            "min": 0.0,
            "max": 0.0,
        }

    return {
        "count": len(values),
        "mean": mean(values),
        "median": median(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "min": min(values),
        "max": max(values),
    }
