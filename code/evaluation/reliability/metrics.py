from __future__ import annotations


def compute_reliability_metrics(results: list[dict]) -> dict[str, float | int]:
    total = len(results)
    passed = sum(1 for item in results if item.get("passed"))
    failures = total - passed
    crash_count = sum(1 for item in results if item.get("crashed"))
    unhandled_errors = sum(item.get("unhandled_errors", 0) for item in results)

    return {
        "total_tests": total,
        "passed_tests": passed,
        "failed_tests": failures,
        "recovery_rate": passed / total if total else 0.0,
        "failure_handling_success_rate": passed / total if total else 0.0,
        "crash_count": crash_count,
        "error_rate": unhandled_errors / total if total else 0.0,
        "unhandled_errors": unhandled_errors,
    }
