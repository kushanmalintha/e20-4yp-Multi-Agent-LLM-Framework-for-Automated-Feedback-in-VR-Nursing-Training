from typing import List, Dict
from app.agents.agent_base import BaseAgent


class PatientAgent(BaseAgent):
    """
    LLM-driven virtual patient for HISTORY step.

    Week-7:
    - Uses BaseAgent infrastructure
    - No evaluation logic
    - No scoring
    - No step control
    """

    async def respond(
        self,
        patient_history: str,
        conversation_history: List[Dict[str, str]],
        student_message: str
    ) -> str:
        """
        Generate a patient response based on history and prior conversation.
        """

        system_prompt = (
            "You are a patient participating in a nursing training simulation.\n"
            "Answer questions truthfully using ONLY the provided patient history.\n"
            "Do not volunteer extra information unless directly asked.\n"
            "Keep responses short, realistic, and consistent.\n"
            "Do NOT give medical advice.\n"
            "Do NOT mention you are an AI.\n"
        )

        conversation_text = ""

        for turn in conversation_history:
            role = turn["speaker"].capitalize()
            conversation_text += f"{role}: {turn['text']}\n"

        user_prompt = (
            f"Patient history:\n{patient_history}\n\n"
            f"Conversation so far:\n{conversation_text}\n"
            f"Student Nurse: {student_message}\n"
            f"Patient:"
        )

        return await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2
        )
