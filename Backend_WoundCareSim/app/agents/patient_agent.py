from typing import List, Dict
from app.agents.agent_base import BaseAgent


class PatientAgent(BaseAgent):
    """
    LLM-driven virtual patient for HISTORY step.
    """

    def _format_patient_history(self, history: Dict) -> str:
        if not history:
            return "No patient history available."

        surgery = history.get("surgery_details", {})
        pain = history.get("pain_level", {})

        return (
            f"PATIENT INFORMATION:\n"
            f"Name: {history.get('name', 'Unknown')}\n"
            f"Age: {history.get('age', 'Unknown')}\n"
            f"Gender: {history.get('gender', 'Unknown')}\n"
            f"Address: {history.get('address', 'Unknown')}\n\n"

            f"MEDICAL BACKGROUND:\n"
            f"Medical Conditions: {', '.join(history.get('medical_history', [])) or 'None'}\n"
            f"Allergies: {', '.join(history.get('allergies', [])) or 'None known'}\n"
            f"Current Medications: {', '.join(history.get('current_medications', [])) or 'None'}\n\n"

            f"SURGICAL INFORMATION:\n"
            f"Recent Procedure: {surgery.get('procedure', 'Unknown')}\n"
            f"Surgery Date: {surgery.get('date', 'Unknown')}\n"
            f"Surgeon: {surgery.get('surgeon', 'Unknown')}\n\n"

            f"PAIN INFORMATION (disclose ONLY when student asks about pain or comfort):\n"
            f"Pain Description: {pain.get('description', 'No pain reported')}\n"
            f"Pain Score (0-10): {pain.get('pain_score', 'Not assessed')}\n\n"

            f"WOUND INFORMATION (disclose ONLY when student asks about the wound):\n"
            f"The wound is a result of the surgical procedure.\n"
        )

    def _fallback_response(self, patient_history: Dict, student_message: str) -> str:
        """
        Return a safe non-LLM fallback when the model call fails.
        """
        message = student_message.lower()
        name = patient_history.get("name", "the patient")
        allergies = patient_history.get("allergies", [])
        pain = patient_history.get("pain_level", {})
        pain_description = pain.get("description") or "There is some discomfort around the wound."
        pain_score = pain.get("pain_score")

        if "name" in message or "who are you" in message:
            return f"My name is {name}."
        if "allerg" in message:
            if allergies:
                return f"I have allergies to {', '.join(allergies)}."
            return "I do not have any known allergies."
        if "pain" in message or "hurt" in message:
            if pain_score is not None:
                return f"{pain_description} I would rate it {pain_score} out of 10."
            return pain_description
        return "I am not sure, but I can answer based on what I know about my condition."

    async def respond(
        self,
        patient_history: Dict,
        conversation_history: List[Dict[str, str]],
        student_message: str
    ) -> str:
        """
        Generate a patient response strictly grounded
        in Firestore scenario data.
        """

        formatted_history = self._format_patient_history(patient_history)

        system_prompt = (
            "You are a patient in a nursing training simulation.\n\n"

            "CRITICAL RULES:\n"
            "1. Answer ONLY using the information provided below. Never invent or assume facts.\n"
            "2. If asked about something NOT in your information, respond naturally:\n"
            "   - 'I am not sure about that'\n"
            "   - 'I do not know'\n"
            "   - 'I cannot remember'\n"
            "3. Do NOT add new medical conditions, symptoms, medications, or history.\n"
            "4. Never contradict the information provided.\n"
            "5. You are NOT a medical professional — speak as an ordinary patient.\n\n"

            "RESPONSE STYLE:\n"
            "- Keep every response to 1 to 2 sentences unless the question genuinely requires more.\n"
            "- Speak naturally and conversationally, as a real patient would.\n"
            "- Be cooperative and polite.\n"
            "- You are conscious, oriented, and able to communicate clearly.\n\n"

            "WHAT NOT TO VOLUNTEER:\n"
            "- Do NOT mention pain, discomfort, or your wound unless the student explicitly "
            "asks about pain, how you are feeling, or your comfort level.\n"
            "- Do NOT bring up your surgical site, the wound, or any physical symptoms "
            "unless directly asked about them.\n"
            "- Answer only what was asked. Do not add unrequested details about your condition.\n\n"

            "AVOIDING REPETITION:\n"
            "- If you have already mentioned something earlier in this conversation, "
            "do NOT repeat it unless the student asks about it again specifically.\n"
            "- If asked the same question twice, give the same answer but do not expand on it.\n\n"

            "PAIN INFORMATION — CONDITIONAL DISCLOSURE:\n"
            "- Your pain details are provided below ONLY for when the student asks about pain or comfort.\n"
            "- Do not reference this information in any other context.\n"
        )

        # Build conversation context
        conversation_text = ""
        for turn in conversation_history:
            role = "Student Nurse" if turn["speaker"] == "student" else "Patient"
            conversation_text += f"{role}: {turn['text']}\n"

        user_prompt = (
            f"{formatted_history}\n"
            f"CONVERSATION SO FAR:\n"
            f"{conversation_text}\n\n"
            f"Student Nurse: {student_message}\n\n"
            "Respond as the patient using ONLY the information provided above."
        )

        response = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0  # deterministic & scenario-faithful
        )
        if not response or response.strip() in {"{}", "[]"}:
            return self._fallback_response(patient_history, student_message)
        return response
