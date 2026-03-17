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


RESULTS_PATH = PROJECT_ROOT / "evaluation" / "reliability" / "results" / "firestore_failures.json"


def sample_scenario() -> dict:
    return {
        "scenario_id": "scenario_firestore_failure",
        "title": "Firestore Failure Scenario",
        "patient_history": {"name": "Mr. Silva", "allergies": [], "pain_level": {"description": "Mild pain", "pain_score": 3}},
        "wound_details": {"type": "Surgical wound"},
        "conversation_points": [],
        "assessment_questions": [],
        "evaluation_criteria": {},
        "vector_namespace": "scenario_firestore_failure",
        "clinical_context": {},
    }


class FakeNarratedFeedback:
    def model_dump(self) -> dict:
        return {"speaker": "system", "step": "history", "message_text": "Feedback returned despite Firestore failure."}


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> dict:
    session_routes.session_manager.sessions.clear()
    session_routes.session_manager.clear_active_session()
    session_routes.conversation_manager.conversations.clear()

    session_id = session_routes.session_manager.create_session(
        scenario_id="scenario_firestore_failure",
        student_id="student_firestore_failure",
        scenario_metadata=sample_scenario(),
    )
    session_routes.conversation_manager.add_turn(session_id, "history", "student", "Hello, I am your nurse today.")
    session_routes.conversation_manager.add_turn(session_id, "history", "patient", "Hello.")

    knowledge_output = EvaluatorResponse(
        agent_name="KnowledgeAgent",
        step="history",
        strengths=["Completed key questions"],
        issues_detected=[],
        explanation="Knowledge evaluation complete.",
        verdict="Appropriate",
        confidence=1.0,
        metadata={
            "identity_asked": True,
            "allergies_asked": True,
            "pain_assessed": True,
            "medical_history_asked": False,
            "procedure_explained": True,
            "risk_factor_assessed": False,
        },
    )
    communication_output = EvaluatorResponse(
        agent_name="CommunicationAgent",
        step="history",
        strengths=["Respectful"],
        issues_detected=[],
        explanation="Communication evaluation complete.",
        verdict="Appropriate",
        confidence=0.9,
        metadata=None,
    )

    with patch.object(session_routes.communication_agent, "evaluate", new=AsyncMock(return_value=communication_output)), patch.object(
        session_routes.knowledge_agent, "evaluate", new=AsyncMock(return_value=knowledge_output)
    ), patch.object(
        session_routes.evaluation_service.feedback_narrator_agent,
        "narrate",
        new=AsyncMock(return_value=FakeNarratedFeedback()),
    ), patch.object(session_routes, "_safe_tts", new=AsyncMock(return_value=None)), patch.object(
        session_routes.StudentLogService, "save_history_step", side_effect=RuntimeError("Firestore unavailable")
    ):
        with TestClient(app) as client:
            response = client.post("/session/complete-step", json={"session_id": session_id, "step": "history"})

    payload = response.json()
    result = {
        "tests": [
            {
                "name": "history_step_firestore_failure",
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
