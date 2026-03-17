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


def summarize(values: Iterable[float]) -> dict[str, float]:
    values = list(values)
    if not values:
        return {"count": 0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "median": 0.0}
    return {
        "count": len(values),
        "mean": mean(values),
        "median": median(values),
        "p50": percentile(values, 0.5),
        "p95": percentile(values, 0.95),
    }


def average_wer(entries: list[dict], field: str = "wer") -> float:
    values = [entry[field] for entry in entries if field in entry]
    return mean(values) if values else 0.0


def average_round_trip_wer(entries: list[dict]) -> float:
    values = [entry["round_trip_wer"] for entry in entries if "round_trip_wer" in entry]
    return mean(values) if values else 0.0
