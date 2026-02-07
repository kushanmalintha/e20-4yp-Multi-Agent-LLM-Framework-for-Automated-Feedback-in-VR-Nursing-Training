from typing import List, Dict
from app.agents.agent_base import BaseAgent


class PatientAgent(BaseAgent):
    """
    LLM-driven virtual patient for HISTORY step.

    REVISED (Week-9):
    - Uses ONLY Firestore scenario data
    - No RAG
    - No hallucination
    - Deterministic and scenario-faithful
    - Natural, realistic patient responses
    """

    def _format_patient_history(self, history: Dict) -> str:
        """
        Convert structured Firestore patient_history
        into an explicit narrative for the LLM.
        """
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
            f"CURRENT PAIN STATUS:\n"
            f"Pain Description: {pain.get('description', 'No pain reported')}\n"
            f"Pain Score (0-10): {pain.get('pain_score', 'Not assessed')}\n\n"
            f"WOUND INFORMATION:\n"
            f"The wound is a result of the surgical procedure.\n"
        )

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
            "1. Answer ONLY using the information provided below\n"
            "2. If asked about something NOT in your information, respond naturally with:\n"
            "   - 'I'm not sure about that'\n"
            "   - 'I don't know'\n"
            "   - 'I can't remember'\n"
            "3. Do NOT guess or make up information\n"
            "4. Do NOT add new medical conditions, symptoms, or history\n"
            "5. Never contradict the given information\n\n"
            "COMMUNICATION STYLE:\n"
            "- Speak naturally and conversationally\n"
            "- Keep responses short and realistic (1-3 sentences typical)\n"
            "- Be cooperative and respectful\n"
            "- Show appropriate emotion (mild discomfort for pain, concern about wound)\n"
            "- You are conscious, oriented, and can communicate clearly\n"
            "- You are NOT a medical professional\n\n"
            "RESPONSE EXAMPLES:\n"
            "Student: 'What is your name?'\n"
            "Patient: 'My name is [Name from data].'\n\n"
            "Student: 'Do you have any allergies?'\n"
            "Patient: '[List allergies from data]' OR 'No, I don't have any allergies.'\n\n"
            "Student: 'Are you experiencing pain?'\n"
            "Patient: '[Describe pain from data]' OR 'Yes, there's some pain at the wound site.'\n\n"
            "Student: 'Do you have diabetes?' (if not in data)\n"
            "Patient: 'No, I don't have diabetes.' OR 'Not that I know of.'\n"
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

        return await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0  # deterministic & scenario-faithful
        )
