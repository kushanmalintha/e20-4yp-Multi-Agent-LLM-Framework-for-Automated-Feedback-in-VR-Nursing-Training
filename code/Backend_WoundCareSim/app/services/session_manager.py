from app.core.state_machine import Step, next_step
from typing import Optional, Dict, Any
from datetime import datetime
import secrets

from app.services.scenario_loader import load_scenario


class SessionManager:
    """
    Manages training sessions.

    Session is the runtime owner of scenario data.
    Firestore is read ONCE at session creation.
    """

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._active_session_id: Optional[str] = None

    # ----------------------------
    # Session lifecycle
    # ----------------------------

    def create_session(
        self,
        scenario_id: str,
        student_id: str,
        scenario_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        session_id = f"sess_{len(self.sessions) + 1}_{int(datetime.now().timestamp())}"

        if scenario_metadata is None:
            scenario_metadata = load_scenario(scenario_id)

        clinical_context = scenario_metadata.get("clinical_context", {})

        self.sessions[session_id] = {
            "scenario_id": scenario_id,
            "student_id": student_id,
            "session_token": secrets.token_urlsafe(24),
            "current_step": Step.HISTORY.value,
            "last_evaluation": None,
            "scenario_metadata": scenario_metadata,
            "clinical_context": clinical_context,
            "logs": [],
            "rag_results": [],
            "action_events": [],
            "mcq_answers": {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.sessions.get(session_id)

    def validate_session_token(self, session_id: str, token: Optional[str]) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False
        if not token:
            return False
        return secrets.compare_digest(session.get("session_token", ""), token)

    # ----------------------------
    # Active session (VR headset join)
    # ----------------------------

    def set_active_session(self, session_id: str) -> None:
        """Mark a session as the currently active VR session."""
        self._active_session_id = session_id

    def get_active_session(self) -> Optional[Dict[str, Any]]:
        """
        Return (session_id, session_token) for the active session,
        or None if no session is currently active.
        """
        if not self._active_session_id:
            return None
        session = self.sessions.get(self._active_session_id)
        if not session:
            self._active_session_id = None
            return None
        return {
            "session_id": self._active_session_id,
            "session_token": session.get("session_token"),
        }

    def clear_active_session(self) -> None:
        """Deactivate the current active session (e.g. after completion)."""
        self._active_session_id = None

    # ----------------------------
    # Evaluation & logging
    # ----------------------------

    def store_last_evaluation(
        self,
        session_id: str,
        evaluation: Dict[str, Any]
    ) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["last_evaluation"] = evaluation
            session["updated_at"] = datetime.now().isoformat()

    def add_log(
        self,
        session_id: str,
        log: Dict[str, Any]
    ) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["logs"].append(log)
            session["updated_at"] = datetime.now().isoformat()

    def add_rag_result(
        self,
        session_id: str,
        rag_result: Dict[str, Any]
    ) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["rag_results"].append(rag_result)

    # ----------------------------
    # Step progression (always allowed)
    # ----------------------------

    def advance_step(self, session_id: str) -> Optional[str]:
        session = self.sessions.get(session_id)
        if not session:
            return None

        current_step = Step(session["current_step"])
        new_step = next_step(current_step)

        session["current_step"] = new_step.value
        session["updated_at"] = datetime.now().isoformat()

        return new_step.value
