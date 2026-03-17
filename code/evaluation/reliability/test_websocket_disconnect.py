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
from app.api import session_routes, websocket_routes


RESULTS_PATH = PROJECT_ROOT / "evaluation" / "reliability" / "results" / "websocket_recovery.json"


def sample_scenario() -> dict:
    return {
        "scenario_id": "scenario_ws_recovery",
        "title": "WebSocket Recovery Scenario",
        "patient_history": {"name": "Mrs. Jayasinghe", "allergies": [], "pain_level": {"description": "Some soreness", "pain_score": 2}},
        "wound_details": {"type": "Surgical wound"},
        "conversation_points": [],
        "assessment_questions": [],
        "evaluation_criteria": {},
        "vector_namespace": "scenario_ws_recovery",
        "clinical_context": {},
    }


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> dict:
    session_routes.session_manager.sessions.clear()
    session_routes.session_manager.clear_active_session()
    session_routes.conversation_manager.conversations.clear()

    session_id = session_routes.session_manager.create_session(
        scenario_id="scenario_ws_recovery",
        student_id="student_ws_recovery",
        scenario_metadata=sample_scenario(),
    )
    token = session_routes.session_manager.get_session(session_id)["session_token"]

    with patch.object(websocket_routes.patient_agent, "respond", new=AsyncMock(side_effect=["Patient response one.", "Patient response two."])), patch.object(
        websocket_routes, "_safe_tts", new=AsyncMock(return_value=None)
    ):
        with TestClient(app) as client:
            with client.websocket_connect(f"/ws/session/{session_id}?token={token}") as websocket:
                websocket.receive_json()
                websocket.send_json(
                    {"type": "event", "event": "text_message", "data": {"text": "First history question"}}
                )
                first_response = websocket.receive_json()

            with client.websocket_connect(f"/ws/session/{session_id}?token={token}") as websocket:
                websocket.receive_json()
                websocket.send_json(
                    {"type": "event", "event": "text_message", "data": {"text": "Second history question"}}
                )
                second_response = websocket.receive_json()

    transcript = session_routes.conversation_manager.get_aggregated_transcript(session_id, "history")
    turns = session_routes.conversation_manager.conversations.get(session_id, {}).get("history", [])
    result = {
        "tests": [
            {
                "name": "websocket_disconnect_recovery",
                "passed": (
                    first_response["event"] == "nurse_message"
                    and second_response["event"] == "nurse_message"
                    and len(turns) == 4
                    and "First history question" in transcript
                    and "Second history question" in transcript
                ),
                "crashed": False,
                "unhandled_errors": 0,
                "details": {
                    "first_response": first_response,
                    "second_response": second_response,
                    "turn_count": len(turns),
                    "transcript": transcript,
                },
            }
        ]
    }
    save_json(RESULTS_PATH, result)
    return result


if __name__ == "__main__":
    main()
