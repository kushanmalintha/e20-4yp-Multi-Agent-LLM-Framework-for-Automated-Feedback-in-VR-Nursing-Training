from typing import Dict, Any, List
from app.utils.action_event import ActionEvent
from app.services.session_manager import SessionManager


class ActionEventService:
    """
    Handles ingestion and storage of student action events.
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    def log_action(
        self,
        session_id: str,
        action_type: str,
        step: str,
        metadata: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        # Validate step consistency
        if session["current_step"] != step:
            raise ValueError(
                f"Action step mismatch: expected {session['current_step']}, got {step}"
            )

        action_event = ActionEvent(
            action_type=action_type,
            step=step,
            metadata=metadata
        )

        # Initialize action log if missing
        if "action_events" not in session:
            session["action_events"] = []

        session["action_events"].append(action_event.to_dict())
        session["updated_at"] = action_event.timestamp

        return action_event.to_dict()
