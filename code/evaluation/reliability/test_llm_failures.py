from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "Backend_WoundCareSim"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app
from app.api import session_routes, websocket_routes
from app.agents.communication_agent import CommunicationAgent
from app.agents.feedback_narrator_agent import FeedbackNarratorAgent
from app.agents.patient_agent import PatientAgent
from app.utils.feedback_schema import Feedback


RESULTS_PATH = PROJECT_ROOT / "evaluation" / "reliability" / "results" / "llm_failures.json"


def sample_scenario() -> dict:
    return {
        "scenario_id": "scenario_reliability",
        "title": "Reliability Scenario",
        "patient_history": {
            "name": "Mr. Fernando",
            "age": 58,
            "gender": "Male",
            "address": "Colombo",
            "medical_history": ["Hypertension"],
            "allergies": ["Penicillin"],
            "current_medications": ["Amlodipine"],
            "surgery_details": {
                "procedure": "Forearm wound closure",
                "date": "2026-03-10",
                "surgeon": "Dr. Silva",
            },
            "pain_level": {
                "description": "There is some pain around the wound.",
                "pain_score": 4,
            },
        },
        "wound_details": {"type": "Surgical wound"},
        "conversation_points": [],
        "assessment_questions": [],
        "evaluation_criteria": {},
        "vector_namespace": "scenario_reliability",
        "clinical_context": {},
    }


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def run_patient_agent_failure() -> dict:
    session_routes.session_manager.sessions.clear()
    session_routes.session_manager.clear_active_session()
    session_routes.conversation_manager.conversations.clear()

    session_id = session_routes.session_manager.create_session(
        scenario_id="scenario_reliability",
        student_id="student_llm_patient",
        scenario_metadata=sample_scenario(),
    )
    token = session_routes.session_manager.get_session(session_id)["session_token"]

    with patch.object(PatientAgent, "run", new=AsyncMock(return_value="{}")), patch.object(
        websocket_routes, "_safe_tts", new=AsyncMock(return_value=None)
    ):
        with TestClient(app) as client:
            with client.websocket_connect(f"/ws/session/{session_id}?token={token}") as websocket:
                websocket.receive_json()
                websocket.send_json(
                    {
                        "type": "event",
                        "event": "text_message",
                        "data": {"text": "Do you have any allergies?"},
                    }
                )
                response = websocket.receive_json()

    passed = (
        response["type"] == "server_event"
        and response["event"] == "nurse_message"
        and response["data"]["text"] == "I have allergies to Penicillin."
    )
    return {
        "name": "patient_agent_llm_failure",
        "passed": passed,
        "crashed": False,
        "unhandled_errors": 0,
        "details": response,
    }


def run_communication_agent_failure() -> dict:
    agent = CommunicationAgent()
    transcript = "\n".join(
        [
            "student: Hello, I am your nurse today.",
            "student: Could you confirm your name for me?",
            "student: I will explain the procedure before we begin.",
        ]
    )

    async def _run():
        with patch.object(CommunicationAgent, "run", new=AsyncMock(return_value="{}")):
            return await agent.evaluate(
                current_step="history",
                student_input=transcript,
                scenario_metadata={},
                rag_response="",
                clinical_context={},
            )

    result = asyncio.run(_run())
    passed = result.verdict in {"Appropriate", "Partially Appropriate", "Inappropriate"}
    return {
        "name": "communication_agent_llm_failure",
        "passed": passed,
        "crashed": False,
        "unhandled_errors": 0,
        "details": result.model_dump(),
    }


def run_feedback_narrator_failure() -> dict:
    agent = FeedbackNarratorAgent()
    raw_feedback = [
        Feedback(
            text="Strengths: introduced self clearly. Areas for improvement: ask more about allergies.",
            speaker="system",
            category="communication",
            timing="post_step",
        ).to_dict()
    ]

    async def _run():
        with patch.object(FeedbackNarratorAgent, "run", new=AsyncMock(return_value="{}")):
            return await agent.narrate(raw_feedback=raw_feedback, step="history", score=72, clinical_context={})

    result = asyncio.run(_run())
    passed = bool(result.message_text) and result.step == "history"
    return {
        "name": "feedback_narrator_llm_failure",
        "passed": passed,
        "crashed": False,
        "unhandled_errors": 0,
        "details": result.model_dump(),
    }


def main() -> dict:
    results = {
        "tests": [
            run_patient_agent_failure(),
            run_communication_agent_failure(),
            run_feedback_narrator_failure(),
        ]
    }
    save_json(RESULTS_PATH, results)
    return results


if __name__ == "__main__":
    main()
