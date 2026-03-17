from typing import Dict, Any, Optional
from datetime import datetime

from app.utils.action_event import ActionEvent
from app.services.session_manager import SessionManager


class ActionEventService:
    """
    Handles ingestion and storage of student action events.
    
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    def record_action(
        self,
        session_id: str,
        action_type: str,
        step: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:

        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        current_step = session["current_step"]

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

        # Week-7: Non-blocking mismatch feedback
        if current_step != step:
            return {
                **action_event.to_dict(),
                "warning": (
                    f"Action recorded for step '{step}' "
                    f"while current step is '{current_step}'."
                )
            }

        return action_event.to_dict()
