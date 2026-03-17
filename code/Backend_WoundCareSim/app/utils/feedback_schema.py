from typing import Literal, Dict, Any


class Feedback:
    """
    Structured feedback unit for VR and UI consumption.
    """

    def __init__(
        self,
        text: str,
        speaker: Literal["patient", "staff_nurse", "system"],
        category: Literal["communication", "knowledge", "clinical"],
        timing: Literal["post_step", "immediate"]
    ):
        self.text = text
        self.speaker = speaker
        self.category = category
        self.timing = timing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "speaker": self.speaker,
            "category": self.category,
            "timing": self.timing
        }
