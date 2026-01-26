from pydantic import BaseModel, Field
from typing import Literal


class NarratedFeedback(BaseModel):
    """
    Student-facing narrated feedback for a single step.

    Designed for:
    - UI display
    - Text-to-Speech (Groq)
    - VR subtitles / overlays
    """

    speaker: Literal["system", "staff_nurse"] = Field(
        default="system",
        description="Who is speaking the feedback"
    )

    step: str = Field(
        ...,
        description="Procedure step this feedback refers to"
    )

    message_text: str = Field(
        ...,
        description="Full narrated feedback paragraph"
    )
