from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.reliability.metrics import compute_reliability_metrics
from evaluation.reliability.test_firestore_failures import main as run_firestore_failures
from evaluation.reliability.test_llm_failures import main as run_llm_failures
from evaluation.reliability.test_rag_failures import main as run_rag_failures
from evaluation.reliability.test_websocket_disconnect import main as run_websocket_recovery


RESULTS_DIR = PROJECT_ROOT / "evaluation" / "reliability" / "results"
SUMMARY_PATH = RESULTS_DIR / "summary.json"


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def flatten(label: str, payload: dict) -> dict:
    tests = payload.get("tests", [])
    passed = all(test.get("passed") for test in tests)
    return {
        "name": label,
        "passed": passed,
        "crashed": any(test.get("crashed") for test in tests),
        "unhandled_errors": sum(test.get("unhandled_errors", 0) for test in tests),
        "tests": tests,
    }


def generate_visualizations(results: list[dict]) -> None:
    import matplotlib.pyplot as plt

    labels = [item["name"] for item in results]
    pass_values = [1 if item["passed"] else 0 for item in results]
    recovery_values = [1 - item["unhandled_errors"] for item in results]

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(labels, pass_values, color=["#2a9d8f" if value else "#e76f51" for value in pass_values])
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("Pass / Fail")
    ax.set_title("Reliability Fault-Injection Results")
    ax.set_yticks([0, 1], labels=["FAIL", "PASS"])
    ax.tick_params(axis="x", rotation=20)
    for bar, value in zip(bars, pass_values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.03, "PASS" if value else "FAIL", ha="center")
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "reliability_pass_fail_chart.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(labels, [max(0, value) for value in recovery_values], color="#264653")
    ax.set_ylabel("Recovery Score")
    ax.set_title("Failure Recovery Rate by Test")
    ax.tick_params(axis="x", rotation=20)
    for bar, value in zip(bars, recovery_values):
        ax.text(bar.get_x() + bar.get_width() / 2, max(0, value) + 0.03, f"{max(0, value):.2f}", ha="center")
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "recovery_rate_chart.png")
    plt.close(fig)


def main() -> dict:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = [
        flatten("LLM failure recovery", run_llm_failures()),
        flatten("RAG failure recovery", run_rag_failures()),
        flatten("Firestore failure recovery", run_firestore_failures()),
        flatten("WebSocket reconnect", run_websocket_recovery()),
    ]
    metrics = compute_reliability_metrics(results)
    payload = {"results": results, "metrics": metrics}
    save_json(SUMMARY_PATH, payload)

    try:
        generate_visualizations(results)
    except ModuleNotFoundError as exc:
        print(f"Visualization skipped: {exc}")

    print("====================================")
    print("Reliability Test Results")
    print("====================================")
    for item in results:
        print(f"{item['name']}: {'PASS' if item['passed'] else 'FAIL'}")
    print("")
    print(f"Recovery Rate: {metrics['recovery_rate']:.0%}")
    print(f"Crash Count: {metrics['crash_count']}")
    print(f"Unhandled Errors: {metrics['unhandled_errors']}")
    print("====================================")

    return payload


if __name__ == "__main__":
    main()
