from __future__ import annotations

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
from app.api import session_routes
from app.utils.schema import EvaluatorResponse


RESULTS_PATH = PROJECT_ROOT / "evaluation" / "reliability" / "results" / "rag_failures.json"


def sample_scenario() -> dict:
    return {
        "scenario_id": "scenario_rag_failure",
        "title": "RAG Failure Scenario",
        "patient_history": {
            "name": "Ms. Perera",
            "age": 42,
            "gender": "Female",
            "address": "Galle",
            "medical_history": ["Diabetes"],
            "allergies": [],
            "current_medications": ["Metformin"],
            "surgery_details": {
                "procedure": "Wound debridement",
                "date": "2026-03-12",
                "surgeon": "Dr. Jayasuriya",
            },
            "pain_level": {"description": "The wound is sore.", "pain_score": 5},
        },
        "wound_details": {"type": "Surgical wound"},
        "conversation_points": [],
        "assessment_questions": [],
        "evaluation_criteria": {},
        "vector_namespace": "scenario_rag_failure",
        "clinical_context": {"risk_factors": ["diabetes"]},
    }


class FakeNarratedFeedback:
    def __init__(self, text: str):
        self.text = text

    def model_dump(self) -> dict:
        return {"speaker": "system", "step": "history", "message_text": self.text}


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> dict:
    session_routes.session_manager.sessions.clear()
    session_routes.session_manager.clear_active_session()
    session_routes.conversation_manager.conversations.clear()

    session_id = session_routes.session_manager.create_session(
        scenario_id="scenario_rag_failure",
        student_id="student_rag_failure",
        scenario_metadata=sample_scenario(),
    )
    session_routes.conversation_manager.add_turn(session_id, "history", "student", "Hello, I am your nurse today.")
    session_routes.conversation_manager.add_turn(session_id, "history", "patient", "Hello nurse.")
    session_routes.conversation_manager.add_turn(session_id, "history", "student", "Do you have pain or diabetes?")
    session_routes.conversation_manager.add_turn(session_id, "history", "patient", "Yes, I have both.")

    knowledge_output = EvaluatorResponse(
        agent_name="KnowledgeAgent",
        step="history",
        strengths=["Asked relevant questions"],
        issues_detected=[],
        explanation="Handled empty RAG context safely.",
        verdict="Appropriate",
        confidence=1.0,
        metadata={
            "identity_asked": False,
            "allergies_asked": False,
            "pain_assessed": True,
            "medical_history_asked": True,
            "procedure_explained": False,
            "risk_factor_assessed": True,
        },
    )
    communication_output = EvaluatorResponse(
        agent_name="CommunicationAgent",
        step="history",
        strengths=["Professional tone"],
        issues_detected=[],
        explanation="Communication remained stable with no RAG context.",
        verdict="Appropriate",
        confidence=0.9,
        metadata=None,
    )

    with patch.object(session_routes, "retrieve_with_rag", new=AsyncMock(return_value={"text": "", "raw_response": None})), patch.object(
        session_routes.communication_agent, "evaluate", new=AsyncMock(return_value=communication_output)
    ), patch.object(
        session_routes.knowledge_agent, "evaluate", new=AsyncMock(return_value=knowledge_output)
    ), patch.object(
        session_routes.evaluation_service.feedback_narrator_agent,
        "narrate",
        new=AsyncMock(return_value=FakeNarratedFeedback("Feedback generated without RAG context.")),
    ), patch.object(session_routes, "_safe_tts", new=AsyncMock(return_value=None)), patch.object(
        session_routes.StudentLogService, "save_history_step", side_effect=Exception("skip persistence")
    ):
        with TestClient(app) as client:
            response = client.post("/session/complete-step", json={"session_id": session_id, "step": "history"})

    payload = response.json()
    result = {
        "tests": [
            {
                "name": "history_pipeline_rag_failure",
                "passed": response.status_code == 200 and bool(payload.get("feedback", {}).get("narrated_feedback")),
                "crashed": False,
                "unhandled_errors": 0,
                "details": payload,
            }
        ]
    }
    save_json(RESULTS_PATH, result)
    return result


if __name__ == "__main__":
    main()
