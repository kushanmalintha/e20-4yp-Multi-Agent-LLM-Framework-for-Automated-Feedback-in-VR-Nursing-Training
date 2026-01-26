from app.agents.agent_base import BaseAgent
from app.core.step_guidance import STEP_GUIDANCE


class StaffNurseAgent(BaseAgent):
    """
    Conversational supervising nurse (GUIDANCE ONLY).

    - Explains the CURRENT step by default
    - Explains the NEXT step ONLY if the student indicates they are finished
    - Does NOT evaluate
    - Does NOT approve or block steps
    - Does NOT decide when a step ends
    """

    FINISH_KEYWORDS = [
        "finished",
        "done",
        "what next",
        "next step",
        "can i proceed",
        "ready",
        "move on"
    ]

    def __init__(self):
        super().__init__()

    def _is_student_finishing(self, student_input: str) -> bool:
        """
        Simple intent detection for step completion.
        This is deterministic and VR-safe.
        """
        student_lower = student_input.lower()
        return any(keyword in student_lower for keyword in self.FINISH_KEYWORDS)

    async def respond(
        self,
        student_input: str,
        current_step: str,
        next_step: str | None
    ) -> str:

        is_finishing = self._is_student_finishing(student_input)

        current_guidance = STEP_GUIDANCE.get(current_step, "")
        next_guidance = STEP_GUIDANCE.get(next_step, "") if next_step else ""

        system_prompt = (
            "You are a supervising staff nurse guiding a nursing student.\n\n"
            "STRICT ROLE RULES:\n"
            "- You provide guidance only.\n"
            "- You do NOT evaluate performance.\n"
            "- You do NOT say whether the student did well or poorly.\n"
            "- You do NOT grant permission to proceed.\n"
            "- You do NOT decide when a step is complete.\n"
            "- The student controls step progression.\n\n"
            "Guidance behavior:\n"
            "- If the student asks what to do now, explain the CURRENT step.\n"
            "- If the student indicates they are finished or asks what is next, "
            "explain the NEXT step.\n"
            "- Keep responses short, clear, and spoken-friendly.\n"
        )

        if is_finishing and next_guidance:
            user_prompt = (
                f"CURRENT STEP: {current_step}\n"
                f"NEXT STEP: {next_step}\n"
                f"NEXT STEP GUIDANCE:\n{next_guidance}\n\n"
                f"STUDENT MESSAGE:\n{student_input}\n"
            )
        else:
            user_prompt = (
                f"CURRENT STEP: {current_step}\n"
                f"CURRENT STEP GUIDANCE:\n{current_guidance}\n\n"
                f"STUDENT MESSAGE:\n{student_input}\n"
            )

        return await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3
        )
