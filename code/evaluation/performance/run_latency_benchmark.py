from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "Backend_WoundCareSim"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app
from app.api import session_routes
from app.core.state_machine import Step
from app.agents.staff_nurse_agent import StaffNurseAgent
from app.services.scenario_loader import load_scenario
from app.services.student_log_service import StudentLogService
from app.utils.feedback_schema import Feedback

from evaluation.performance.metrics import summarize_latencies


RESULTS_DIR = PROJECT_ROOT / "evaluation" / "performance" / "results"
RESULTS_PATH = RESULTS_DIR / "latency_results.json"
DEFAULT_ITERATIONS = 20


class FakeNarratedFeedback:
    def __init__(self, message_text: str):
        self.message_text = message_text

    def model_dump(self) -> dict[str, Any]:
        return {
            "speaker": "system",
            "step": "history",
            "message_text": self.message_text,
        }


def ensure_env() -> None:
    required = ["OPENAI_API_KEY"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_scenario_sample() -> dict[str, Any]:
    return load_scenario("scenario_001")


async def benchmark_patient_response(iterations: int, scenario_metadata: dict[str, Any]) -> list[float]:
    latencies = []
    patient_history = scenario_metadata["patient_history"]
    history = [{"speaker": "student", "text": "Hello, I am your nurse today."}]

    for _ in range(iterations):
        start = time.perf_counter()
        response = await session_routes.patient_agent.respond(
            patient_history=patient_history,
            conversation_history=history,
            student_message="Do you have any allergies and pain right now?",
        )
        await session_routes._safe_tts(response, role="patient")
        latencies.append(time.perf_counter() - start)

    return latencies


async def benchmark_action_feedback(iterations: int) -> list[float]:
    latencies = []
    performed_actions = [{"action_type": "action_initial_hand_hygiene"}]

    for _ in range(iterations):
        start = time.perf_counter()
        await session_routes.clinical_agent.get_real_time_feedback(
            action_type="action_clean_trolley",
            performed_actions=performed_actions,
            rag_guidelines="Follow aseptic wound preparation steps.",
            clinical_context={"risk_factors": ["diabetes"]},
        )
        latencies.append(time.perf_counter() - start)

    return latencies


async def benchmark_nurse_verification(iterations: int) -> list[float]:
    latencies = []
    nurse_agent = StaffNurseAgent()
    for _ in range(iterations):
        start = time.perf_counter()
        verdict = await nurse_agent.verify_material_conversational(
            student_message="This is the surgical spirit bottle. It is sealed, intact, and expires next year.",
            material_type="solution",
            clinical_context={"risk_factors": ["diabetes"]},
        )
        await session_routes._safe_tts(verdict["message"], role="staff_nurse")
        latencies.append(time.perf_counter() - start)

    return latencies


async def benchmark_history_evaluation(
    iterations: int,
    scenario_metadata: dict[str, Any],
) -> tuple[list[float], dict[str, list[float]]]:
    total_latencies = []
    stage_breakdown = {
        "rag": [],
        "knowledge_agent": [],
        "communication_agent": [],
        "feedback_narrator_agent": [],
    }
    transcript = "\n".join(
        [
            "student: Hello, I am your nurse today.",
            "student: Can you confirm your full name and date of birth?",
            "student: Do you have any allergies?",
            "student: How much pain are you feeling?",
            "student: Do you have diabetes or any medical history that affects healing?",
            "student: I will explain the procedure before we begin.",
        ]
    )
    clinical_context = {"risk_factors": ["diabetes"], "healing_risk": "high", "infection_risk": "high"}

    for _ in range(iterations):
        overall_start = time.perf_counter()

        rag_start = time.perf_counter()
        rag = await session_routes.retrieve_with_rag(
            query="patient history taking guidelines nursing communication assessment questions diabetic patient",
            scenario_id="scenario_001",
        )
        stage_breakdown["rag"].append(time.perf_counter() - rag_start)

        knowledge_start = time.perf_counter()
        knowledge_output = await session_routes.knowledge_agent.evaluate(
            current_step="history",
            student_input=transcript,
            scenario_metadata=scenario_metadata,
            rag_response=rag.get("text", ""),
            clinical_context=clinical_context,
        )
        stage_breakdown["knowledge_agent"].append(time.perf_counter() - knowledge_start)

        communication_start = time.perf_counter()
        communication_output = await session_routes.communication_agent.evaluate(
            current_step="history",
            student_input=transcript,
            scenario_metadata=scenario_metadata,
            rag_response=rag.get("text", ""),
            clinical_context=clinical_context,
        )
        stage_breakdown["communication_agent"].append(time.perf_counter() - communication_start)

        score = session_routes.evaluation_service.aggregate_evaluations.__globals__["aggregate_scores"](
            evaluations=[knowledge_output, communication_output],
            current_step="history",
            clinical_context=clinical_context,
        )
        raw_feedback = []
        for output in [communication_output, knowledge_output]:
            parts = []
            if output.strengths:
                parts.append("Strengths: " + ", ".join(output.strengths))
            if output.issues_detected:
                parts.append("Areas for improvement: " + ", ".join(output.issues_detected))
            if output.explanation:
                parts.append(output.explanation)
            raw_feedback.append(
                Feedback(
                    text=" ".join(parts),
                    speaker="system",
                    category="communication" if output.agent_name == "CommunicationAgent" else "knowledge",
                    timing="post_step",
                ).to_dict()
            )

        narrator_start = time.perf_counter()
        await session_routes.evaluation_service.feedback_narrator_agent.narrate(
            raw_feedback=raw_feedback,
            step="history",
            score=round((score.get("step_quality_indicator") or 0.0) * 100),
            clinical_context=clinical_context,
        )
        stage_breakdown["feedback_narrator_agent"].append(time.perf_counter() - narrator_start)

        total_latencies.append(time.perf_counter() - overall_start)

    return total_latencies, stage_breakdown


async def benchmark_mcq_evaluation(iterations: int, scenario_metadata: dict[str, Any]) -> list[float]:
    latencies = []
    questions = scenario_metadata["assessment_questions"]
    answers = {questions[0]["id"]: questions[0]["correct_answer"], questions[1]["id"]: "wrong"}

    for _ in range(iterations):
        start = time.perf_counter()
        session_routes.mcq_evaluator.validate_mcq_answers(
            student_answers=answers,
            assessment_questions=questions,
        )
        latencies.append(time.perf_counter() - start)

    return latencies


def benchmark_session_start(iterations: int) -> list[float]:
    latencies = []
    with TestClient(app) as client:
        for idx in range(iterations):
            start = time.perf_counter()
            response = client.post(
                "/session/start",
                json={"scenario_id": "scenario_001", "student_id": f"perf_student_{idx}"},
            )
            response.raise_for_status()
            latencies.append(time.perf_counter() - start)
    return latencies


def build_log_session(session_id: str, scenario_metadata: dict[str, Any]) -> dict[str, Any]:
    session = session_routes.session_manager.get_session(session_id)
    session_routes.conversation_manager.add_turn(session_id, Step.HISTORY.value, "student", "Hello, I am your nurse today.")
    session_routes.conversation_manager.add_turn(session_id, Step.HISTORY.value, "patient", "Hello nurse.")
    session["last_evaluation"] = {
        "step": "history",
        "scores": {
            "step_quality_indicator": 0.9,
            "interpretation": "Excellent history-taking performance",
            "agent_scores": {"KnowledgeAgent": 1.0, "CommunicationAgent": 1.0},
        },
        "agent_feedback": {
            "CommunicationAgent": {
                "verdict": "Appropriate",
                "strengths": ["Professional introduction"],
                "issues_detected": [],
            }
        },
        "narrated_feedback": {"message_text": "Strong communication and information gathering."},
    }
    session["mcq_answers"] = {q["id"]: q["correct_answer"] for q in scenario_metadata["assessment_questions"]}
    session["action_events"] = [
        {"action_type": "action_initial_hand_hygiene", "timestamp": "2026-03-14T00:00:00"},
        {"action_type": "action_clean_trolley", "timestamp": "2026-03-14T00:01:00"},
        {"action_type": "action_hand_hygiene_after_cleaning", "timestamp": "2026-03-14T00:02:00"},
        {"action_type": "action_select_solution", "timestamp": "2026-03-14T00:03:00"},
        {"action_type": "action_verify_solution", "timestamp": "2026-03-14T00:04:00"},
        {"action_type": "action_select_dressing", "timestamp": "2026-03-14T00:05:00"},
        {"action_type": "action_verify_dressing", "timestamp": "2026-03-14T00:06:00"},
    ]
    session["current_step"] = "completed"
    return StudentLogService.generate(
        session_id=session_id,
        session_manager=session_routes.session_manager,
        conversation_manager=session_routes.conversation_manager,
    )


def benchmark_firestore_write(iterations: int, scenario_metadata: dict[str, Any]) -> list[float]:
    latencies = []
    for idx in range(iterations):
        session_id = session_routes.session_manager.create_session(
            scenario_id="scenario_001",
            student_id=f"log_student_{idx}",
            scenario_metadata=scenario_metadata,
        )
        log = build_log_session(session_id, scenario_metadata)
        start = time.perf_counter()
        StudentLogService.save_to_firestore(log)
        latencies.append(time.perf_counter() - start)
    return latencies


async def main() -> None:
    ensure_env()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    scenario_metadata = load_scenario_sample()

    patient_response = await benchmark_patient_response(DEFAULT_ITERATIONS, scenario_metadata)
    action_feedback = await benchmark_action_feedback(DEFAULT_ITERATIONS)
    nurse_verification = await benchmark_nurse_verification(DEFAULT_ITERATIONS)
    history_total, history_stages = await benchmark_history_evaluation(DEFAULT_ITERATIONS, scenario_metadata)
    mcq_evaluation = await benchmark_mcq_evaluation(DEFAULT_ITERATIONS, scenario_metadata)
    session_start = benchmark_session_start(DEFAULT_ITERATIONS)
    firestore_log_write = benchmark_firestore_write(DEFAULT_ITERATIONS, scenario_metadata)

    results = {
        "iterations": DEFAULT_ITERATIONS,
        "latencies_seconds": {
            "patient_response": patient_response,
            "action_feedback": action_feedback,
            "nurse_verification": nurse_verification,
            "history_evaluation": history_total,
            "mcq_evaluation": mcq_evaluation,
            "session_start": session_start,
            "firestore_log_write": firestore_log_write,
        },
        "history_evaluation_stage_breakdown_seconds": history_stages,
        "summary": {
            "patient_response": summarize_latencies(patient_response),
            "action_feedback": summarize_latencies(action_feedback),
            "nurse_verification": summarize_latencies(nurse_verification),
            "history_evaluation": summarize_latencies(history_total),
            "mcq_evaluation": summarize_latencies(mcq_evaluation),
            "session_start": summarize_latencies(session_start),
            "firestore_log_write": summarize_latencies(firestore_log_write),
        },
    }
    results["history_evaluation_stage_summary"] = {
        stage: summarize_latencies(values) for stage, values in history_stages.items()
    }
    save_json(RESULTS_PATH, results)

    print("====================================")
    print("Latency Results")
    print("====================================")
    print(f"{'Operation':25} {'P50':>8} {'P95':>8}")
    print("------------------------------------")
    for name, summary in results["summary"].items():
        print(f"{name:25} {summary['p50']:>8.2f}s {summary['p95']:>8.2f}s")
    print("\nSaved to:")
    print(RESULTS_PATH)


if __name__ == "__main__":
    asyncio.run(main())
