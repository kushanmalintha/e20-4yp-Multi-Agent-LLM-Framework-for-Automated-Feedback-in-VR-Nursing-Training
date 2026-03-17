from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.performance.metrics import summarize_latencies


RESULTS_DIR = PROJECT_ROOT / "evaluation" / "performance" / "results"
LATENCY_RESULTS_PATH = RESULTS_DIR / "latency_results.json"
CONCURRENT_RESULTS_PATH = RESULTS_DIR / "concurrent_results.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def plot_latency_bar_chart(latency_results: dict) -> None:
    import matplotlib.pyplot as plt

    operations = list(latency_results["latencies_seconds"].keys())
    p50_values = [latency_results["summary"][name]["p50"] for name in operations]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(operations, p50_values, color="#2a9d8f")
    ax.set_ylabel("P50 latency (s)")
    ax.set_title("Operation Latency Benchmarks")
    ax.tick_params(axis="x", rotation=25)
    for bar, value in zip(bars, p50_values):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.2f}s", ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "latency_bar_chart.png")
    plt.close(fig)


def plot_latency_histograms(latency_results: dict) -> None:
    import matplotlib.pyplot as plt

    operations = latency_results["latencies_seconds"]
    fig, axes = plt.subplots(len(operations), 1, figsize=(9, 3 * len(operations)))
    if len(operations) == 1:
        axes = [axes]

    for ax, (name, values) in zip(axes, operations.items()):
        ax.hist(values, bins=min(10, len(values)), color="#e9c46a", edgecolor="#333333")
        summary = summarize_latencies(values)
        ax.set_title(f"{name} distribution (P50={summary['p50']:.2f}s, P95={summary['p95']:.2f}s)")
        ax.set_xlabel("Latency (s)")
        ax.set_ylabel("Frequency")

    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "latency_histograms.png")
    plt.close(fig)


def plot_history_stage_breakdown(latency_results: dict) -> None:
    import matplotlib.pyplot as plt

    stage_summary = latency_results["history_evaluation_stage_summary"]
    stages = list(stage_summary.keys())
    p50_values = [stage_summary[stage]["p50"] for stage in stages]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(stages, p50_values, color=["#264653", "#2a9d8f", "#e9c46a", "#f4a261"])
    ax.set_ylabel("P50 latency (s)")
    ax.set_title("History Evaluation Stage Breakdown")
    ax.tick_params(axis="x", rotation=20)
    for bar, value in zip(bars, p50_values):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.2f}s", ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "history_stage_breakdown.png")
    plt.close(fig)


def plot_concurrent_summary(concurrent_results: dict) -> None:
    import matplotlib.pyplot as plt

    operation_summary = concurrent_results["summary"]["operation_summary"]
    operations = list(operation_summary.keys())
    p50_values = [operation_summary[name]["p50"] for name in operations]
    p95_values = [operation_summary[name]["p95"] for name in operations]

    fig, ax = plt.subplots(figsize=(9, 5))
    x_positions = range(len(operations))
    ax.bar([x - 0.2 for x in x_positions], p50_values, width=0.4, label="P50", color="#2a9d8f")
    ax.bar([x + 0.2 for x in x_positions], p95_values, width=0.4, label="P95", color="#e76f51")
    ax.set_xticks(list(x_positions), operations, rotation=20)
    ax.set_ylabel("Latency (s)")
    ax.set_title("Concurrent Session Request Latencies")
    ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "concurrent_request_latencies.png")
    plt.close(fig)


def main() -> None:
    if not LATENCY_RESULTS_PATH.exists():
        raise FileNotFoundError(f"Missing latency results: {LATENCY_RESULTS_PATH}")

    latency_results = load_json(LATENCY_RESULTS_PATH)
    plot_latency_bar_chart(latency_results)
    plot_latency_histograms(latency_results)
    plot_history_stage_breakdown(latency_results)

    if CONCURRENT_RESULTS_PATH.exists():
        concurrent_results = load_json(CONCURRENT_RESULTS_PATH)
        plot_concurrent_summary(concurrent_results)

    print("Charts saved to:")
    print(RESULTS_DIR)


if __name__ == "__main__":
    main()
