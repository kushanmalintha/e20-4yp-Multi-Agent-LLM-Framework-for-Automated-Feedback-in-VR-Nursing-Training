from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "Backend_WoundCareSim"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app
from app.api import session_routes
from app.core.state_machine import Step

from evaluation.performance.metrics import summarize_latencies


RESULTS_DIR = PROJECT_ROOT / "evaluation" / "performance" / "results"
RESULTS_PATH = RESULTS_DIR / "concurrent_results.json"
CONCURRENT_SESSIONS = 5


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


async def timed_post(client: httpx.AsyncClient, url: str, json_payload: dict[str, Any]) -> tuple[float, httpx.Response]:
    start = time.perf_counter()
    response = await client.post(url, json=json_payload)
    return time.perf_counter() - start, response


def inject_history(session_id: str, session_index: int) -> None:
    messages = [
        f"Hello, I am nurse {session_index}.",
        "Can you confirm your name and date of birth?",
        "Do you have allergies or pain today?",
    ]
    for message in messages:
        session_routes.conversation_manager.add_turn(session_id, Step.HISTORY.value, "student", message)
        session_routes.conversation_manager.add_turn(session_id, Step.HISTORY.value, "patient", "Sample patient reply.")


def inject_assessment(session_id: str) -> None:
    session = session_routes.session_manager.get_session(session_id)
    questions = session["scenario_metadata"]["assessment_questions"]
    session["mcq_answers"] = {
        questions[0]["id"]: questions[0]["correct_answer"],
        questions[1]["id"]: questions[1]["correct_answer"],
    }


def inject_actions(session_id: str) -> None:
    session = session_routes.session_manager.get_session(session_id)
    session["action_events"] = [
        {"action_type": "action_initial_hand_hygiene", "timestamp": "2026-03-14T00:00:00"},
        {"action_type": "action_clean_trolley", "timestamp": "2026-03-14T00:01:00"},
        {"action_type": "action_hand_hygiene_after_cleaning", "timestamp": "2026-03-14T00:02:00"},
        {"action_type": "action_select_solution", "timestamp": "2026-03-14T00:03:00"},
        {"action_type": "action_verify_solution", "timestamp": "2026-03-14T00:04:00"},
        {"action_type": "action_select_dressing", "timestamp": "2026-03-14T00:05:00"},
        {"action_type": "action_verify_dressing", "timestamp": "2026-03-14T00:06:00"},
        {"action_type": "action_arrange_materials", "timestamp": "2026-03-14T00:07:00"},
        {"action_type": "action_bring_trolley", "timestamp": "2026-03-14T00:08:00"},
    ]


async def run_single_session(session_index: int) -> dict[str, Any]:
    transport = httpx.ASGITransport(app=app)
    request_latencies = []
    errors = []

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        latency, start_response = await timed_post(
            client,
            "/session/start",
            {"scenario_id": "scenario_001", "student_id": f"concurrent_student_{session_index}"},
        )
        request_latencies.append({"operation": "session_start", "latency": latency, "status_code": start_response.status_code})
        if start_response.status_code != 200:
            errors.append(f"session_start:{start_response.status_code}")
            return {"session_index": session_index, "request_latencies": request_latencies, "errors": errors, "session_isolation_issue": True}

        session_id = start_response.json()["session_id"]
        inject_history(session_id, session_index)
        latency, history_response = await timed_post(
            client,
            "/session/complete-step",
            {"session_id": session_id, "step": "history"},
        )
        request_latencies.append({"operation": "complete_history", "latency": latency, "status_code": history_response.status_code})
        if history_response.status_code != 200:
            errors.append(f"complete_history:{history_response.status_code}")

        inject_assessment(session_id)
        latency, assessment_response = await timed_post(
            client,
            "/session/complete-step",
            {"session_id": session_id, "step": "assessment"},
        )
        request_latencies.append({"operation": "complete_assessment", "latency": latency, "status_code": assessment_response.status_code})
        if assessment_response.status_code != 200:
            errors.append(f"complete_assessment:{assessment_response.status_code}")

        inject_actions(session_id)
        latency, cleaning_response = await timed_post(
            client,
            "/session/complete-step",
            {"session_id": session_id, "step": "cleaning_and_dressing"},
        )
        request_latencies.append({"operation": "complete_cleaning", "latency": latency, "status_code": cleaning_response.status_code})
        if cleaning_response.status_code != 200:
            errors.append(f"complete_cleaning:{cleaning_response.status_code}")

        final_session = session_routes.session_manager.get_session(session_id)
        isolation_issue = False
        if not final_session or final_session.get("student_id") != f"concurrent_student_{session_index}":
            isolation_issue = True
        history_turns = session_routes.conversation_manager.conversations.get(session_id, {}).get("history", [])
        if any(f"nurse {session_index}" not in turn["text"].lower() for turn in history_turns if turn["speaker"] == "student"):
            isolation_issue = True
        if cleaning_response.status_code == 200 and cleaning_response.json().get("next_step") != "completed":
            isolation_issue = True

    return {
        "session_index": session_index,
        "session_id": session_id,
        "request_latencies": request_latencies,
        "errors": errors,
        "session_isolation_issue": isolation_issue,
    }


async def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    session_results = await asyncio.gather(*(run_single_session(idx) for idx in range(CONCURRENT_SESSIONS)))
    total_duration = time.perf_counter() - started

    all_latencies = [entry["latency"] for result in session_results for entry in result["request_latencies"]]
    error_count = sum(len(result["errors"]) for result in session_results)
    total_requests = sum(len(result["request_latencies"]) for result in session_results)
    isolation_issues = [result for result in session_results if result["session_isolation_issue"]]

    operation_summary = {}
    operations = sorted({entry["operation"] for result in session_results for entry in result["request_latencies"]})
    for operation in operations:
        latencies = [
            entry["latency"]
            for result in session_results
            for entry in result["request_latencies"]
            if entry["operation"] == operation
        ]
        operation_summary[operation] = summarize_latencies(latencies)

    payload = {
        "concurrent_sessions": CONCURRENT_SESSIONS,
        "total_duration_seconds": total_duration,
        "session_results": session_results,
        "summary": {
            "all_requests": summarize_latencies(all_latencies),
            "error_rate": error_count / total_requests if total_requests else 0.0,
            "error_count": error_count,
            "total_requests": total_requests,
            "session_isolation_issues": len(isolation_issues),
            "operation_summary": operation_summary,
        },
    }
    save_json(RESULTS_PATH, payload)

    print("====================================")
    print("Concurrent Session Results")
    print("====================================")
    print(f"Concurrent sessions: {CONCURRENT_SESSIONS}")
    print(f"Total requests: {total_requests}")
    print(f"Error rate: {payload['summary']['error_rate']:.2%}")
    print(f"Session isolation issues: {payload['summary']['session_isolation_issues']}")
    print(f"Overall P50: {payload['summary']['all_requests']['p50']:.2f}s")
    print(f"Overall P95: {payload['summary']['all_requests']['p95']:.2f}s")
    print("\nSaved to:")
    print(RESULTS_PATH)


if __name__ == "__main__":
    asyncio.run(main())
