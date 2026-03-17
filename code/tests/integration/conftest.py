from __future__ import annotations

import copy
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.utils.schema import EvaluatorResponse


class FakeNarratedFeedback:
    def __init__(self, message_text: str):
        self.message_text = message_text

    def model_dump(self) -> dict:
        return {
            "speaker": "system",
            "step": "history",
            "message_text": self.message_text,
        }


@pytest.fixture
def sample_scenario_metadata():
    return {
        "scenario_id": "scenario_001",
        "title": "Post-operative Wound Care",
        "patient_history": "Patient had minor surgery and needs wound-care preparation.",
        "wound_details": {
            "type": "Surgical wound",
            "location": "Left forearm",
        },
        "conversation_points": [
            "Confirm identity",
            "Check allergies",
            "Assess pain",
        ],
        "assessment_questions": [
            {
                "id": "q1",
                "question": "What type of wound is present?",
                "options": ["Surgical wound", "Burn"],
                "correct_answer": "Surgical wound",
                "explanation": "This is a post-operative surgical wound.",
            },
            {
                "id": "q2",
                "question": "Where is the wound located?",
                "options": ["Left forearm", "Right leg"],
                "correct_answer": "Left forearm",
                "explanation": "The wound is on the left forearm.",
            },
        ],
        "evaluation_criteria": {},
        "vector_namespace": "scenario_001",
        "clinical_context": {"risk_factors": ["diabetes"]},
    }


@pytest.fixture
def app_modules(monkeypatch, sample_scenario_metadata):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("VECTOR_STORE_ID", "vs_test")
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")

    main = importlib.import_module("app.main")
    session_routes = importlib.import_module("app.api.session_routes")
    websocket_routes = importlib.import_module("app.api.websocket_routes")
    scenario_routes = importlib.import_module("app.api.scenario_routes")
    session_manager_module = importlib.import_module("app.services.session_manager")
    evaluation_service_module = importlib.import_module("app.services.evaluation_service")

    session_routes.session_manager.sessions.clear()
    session_routes.session_manager.clear_active_session()
    session_routes.conversation_manager.conversations.clear()

    def fake_load_scenario(scenario_id: str):
        payload = copy.deepcopy(sample_scenario_metadata)
        payload["scenario_id"] = scenario_id
        payload["vector_namespace"] = scenario_id
        return payload

    async def fake_retrieve_with_rag(*args, **kwargs):
        return {"text": "Retrieved guideline text", "raw_response": {"id": "rag_1"}}

    async def fake_extract_prerequisite_map(*args, **kwargs):
        return copy.deepcopy(session_routes.clinical_agent.PREREQUISITE_MAP)

    async def fake_tts(*args, **kwargs):
        return None

    async def fake_sleep(*args, **kwargs):
        return None

    def fake_save(*args, **kwargs):
        return "students/student_001/sessions/mock"

    knowledge_response = EvaluatorResponse(
        agent_name="KnowledgeAgent",
        step="history",
        strengths=["Confirmed identity", "Checked allergies"],
        issues_detected=[],
        explanation="Knowledge checks were completed correctly.",
        verdict="Appropriate",
        confidence=0.95,
        metadata={
            "identity_asked": True,
            "allergies_asked": True,
            "pain_assessed": True,
            "medical_history_asked": True,
            "procedure_explained": True,
            "risk_factor_assessed": True,
        },
    )
    communication_response = EvaluatorResponse(
        agent_name="CommunicationAgent",
        step="history",
        strengths=["Clear communication"],
        issues_detected=[],
        explanation="Communication was professional and appropriate.",
        verdict="Appropriate",
        confidence=0.9,
        metadata=None,
    )

    monkeypatch.setattr(session_manager_module, "load_scenario", fake_load_scenario)
    monkeypatch.setattr(session_routes, "retrieve_with_rag", fake_retrieve_with_rag)
    monkeypatch.setattr(websocket_routes, "retrieve_with_rag", fake_retrieve_with_rag)
    monkeypatch.setattr(evaluation_service_module, "retrieve_with_rag", fake_retrieve_with_rag)
    monkeypatch.setattr(session_routes, "extract_prerequisite_map", fake_extract_prerequisite_map)
    monkeypatch.setattr(session_routes, "_safe_tts", fake_tts)
    monkeypatch.setattr(websocket_routes, "_safe_tts", fake_tts)
    monkeypatch.setattr(websocket_routes.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(
        session_routes.communication_agent,
        "evaluate",
        AsyncMock(return_value=communication_response),
    )
    monkeypatch.setattr(
        session_routes.knowledge_agent,
        "evaluate",
        AsyncMock(return_value=knowledge_response),
    )
    monkeypatch.setattr(
        session_routes.evaluation_service.feedback_narrator_agent,
        "narrate",
        AsyncMock(return_value=FakeNarratedFeedback("Narrated history feedback")),
    )
    monkeypatch.setattr(
        session_routes.clinical_agent,
        "_explain_missing_prerequisites",
        AsyncMock(return_value="You must complete the earlier preparation steps first."),
    )
    monkeypatch.setattr(
        websocket_routes.clinical_agent,
        "_explain_missing_prerequisites",
        AsyncMock(return_value="You must complete the earlier preparation steps first."),
    )
    monkeypatch.setattr(session_routes.StudentLogService, "save_history_step", staticmethod(fake_save))
    monkeypatch.setattr(session_routes.StudentLogService, "save_assessment_step", staticmethod(fake_save))
    monkeypatch.setattr(session_routes.StudentLogService, "save_cleaning_step", staticmethod(fake_save))
    monkeypatch.setattr(session_routes.StudentLogService, "save_to_firestore", staticmethod(fake_save))
    monkeypatch.setattr(websocket_routes.StudentLogService, "save_history_step", staticmethod(fake_save))
    monkeypatch.setattr(websocket_routes.StudentLogService, "save_assessment_step", staticmethod(fake_save))
    monkeypatch.setattr(websocket_routes.StudentLogService, "save_cleaning_step", staticmethod(fake_save))
    monkeypatch.setattr(
        scenario_routes,
        "list_scenarios",
        lambda: [
            {
                "scenario_id": "scenario_001",
                "scenario_title": "Post-operative Wound Care",
            }
        ],
    )

    return SimpleNamespace(
        app=main.app,
        session_routes=session_routes,
        websocket_routes=websocket_routes,
        scenario_routes=scenario_routes,
    )


@pytest.fixture
def client(app_modules):
    with TestClient(app_modules.app) as test_client:
        yield test_client


@pytest.fixture
def start_session(client):
    def _start_session():
        response = client.post(
            "/session/start",
            json={"scenario_id": "scenario_001", "student_id": "student_001"},
        )
        assert response.status_code == 200
        return response.json()

    return _start_session
