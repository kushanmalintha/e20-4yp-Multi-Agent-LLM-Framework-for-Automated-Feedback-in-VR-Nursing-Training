from typing import List, Dict, Any
import json

from app.agents.agent_base import BaseAgent
from app.utils.narrated_feedback_schema import NarratedFeedback


class FeedbackNarratorAgent(BaseAgent):
    """
    Presentation-only LLM agent.

    Converts raw backend feedback into a single
    student-friendly narrated paragraph.
    """

    def __init__(self):
        super().__init__()

    async def narrate(
        self,
        raw_feedback: List[Dict[str, Any]],
        step: str
    ) -> NarratedFeedback:

        system_prompt = self._build_system_prompt(step)
        user_prompt = self._build_user_prompt(raw_feedback)

        output_text = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3
        )

        return self._parse_output(output_text, raw_feedback, step)

    # --------------------------------------------------
    # Prompt construction
    # --------------------------------------------------

    def _build_system_prompt(self, step: str) -> str:
        return f"""
You are a nursing education tutor.

Your task is to rewrite backend-generated feedback
into ONE clear, supportive paragraph addressed to the student.

Context:
- Formative nursing education
- Step: {step}

Rules:
- Do NOT add new medical advice
- Do NOT contradict the feedback
- Do NOT change meaning
- Be supportive and professional
- Keep the paragraph concise
- Output RAW JSON only
- Do NOT include markdown or extra text

Required JSON format:
{{
  "speaker": "system",
  "message_text": "..."
}}
"""

    def _build_user_prompt(self, raw_feedback: List[Dict[str, Any]]) -> str:
        return f"""
Raw backend feedback (JSON list):

{json.dumps(raw_feedback, indent=2)}

Combine this feedback into ONE paragraph that:
- Mentions strengths first (if any)
- Then mentions areas for improvement (if any)
- Ends with an encouraging closing sentence
"""

    # --------------------------------------------------
    # Output parsing with safe fallback
    # --------------------------------------------------

    def _parse_output(
        self,
        output_text: str,
        raw_feedback: List[Dict[str, Any]],
        step: str
    ) -> NarratedFeedback:

        try:
            parsed = json.loads(output_text)

            return NarratedFeedback(
                speaker=parsed.get("speaker", "system"),
                step=step,
                message_text=parsed["message_text"]
            )

        except Exception:
            # Fallback: concatenate raw feedback texts
            combined_text = " ".join(
                item.get("text", "") for item in raw_feedback
            )

            return NarratedFeedback(
                speaker="system",
                step=step,
                message_text=combined_text
            )
