from typing import Dict, Any, Optional
from datetime import datetime


class ActionEvent:
    """
    Represents a symbolic student action.
    Used for future VR and procedural evaluation.
    """

    def __init__(
        self,
        action_type: str,
        step: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.action_type = action_type
        self.step = step
        self.timestamp = datetime.utcnow().isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "step": self.step,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
