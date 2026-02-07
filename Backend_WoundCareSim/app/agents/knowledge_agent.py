import json

from pydantic import ValidationError
from app.agents.agent_base import BaseAgent
from app.utils.schema import EvaluatorResponse

class KnowledgeAgent(BaseAgent):
    """
    Evaluates the student's clinical knowledge and information gathering during history taking.
    Focuses on: completeness of history, appropriate questions, clinical reasoning.
    """

    def __init__(self):
        super().__init__()

    async def evaluate(
        self,
        current_step: str,
        student_input: str,
        scenario_metadata: dict,
        rag_response: str,
    ) -> EvaluatorResponse:
        """
        Evaluate clinical knowledge and information gathering completeness.
        """

        # CRITICAL: Check for empty input first
        if current_step == "history" and (not student_input or student_input.strip() == ""):
            return EvaluatorResponse(
                agent_name="KnowledgeAgent",
                step=current_step,
                strengths=[],
                issues_detected=[
                    "No patient history obtained",
                    "Failed to gather critical medical information",
                    "Cannot assess patient safety without complete history"
                ],
                explanation="The student did not gather any patient history. Understanding the patient's medical background, allergies, current medications, pain level, and surgical history is essential for safe wound care. Without this knowledge, the student cannot make informed clinical decisions or ensure patient safety.",
                verdict="Inappropriate",
                confidence=1.0
            )

        system_prompt = (
            "You are a nursing clinical knowledge evaluator for history-taking.\n\n"
            "ROLE: Evaluate ONLY the completeness and appropriateness of information gathered, NOT communication style.\n\n"
            "ESSENTIAL INFORMATION TO ASSESS:\n"
            "1. Patient Identity Verification\n"
            "   - Name, age, address\n"
            "   - Why critical: Prevents wrong-patient errors\n\n"
            "2. Allergy Assessment (HIGHEST PRIORITY)\n"
            "   - Medication allergies\n"
            "   - Dressing/tape/latex allergies\n"
            "   - Why critical: Prevents life-threatening reactions, guides material selection\n\n"
            "3. Pain Assessment\n"
            "   - Presence of pain\n"
            "   - Pain severity/description\n"
            "   - Why critical: Ensures comfort, identifies complications\n\n"
            "4. Medical History\n"
            "   - Current medical conditions\n"
            "   - Recent surgery/procedure details\n"
            "   - Current medications\n"
            "   - Why critical: Identifies risk factors, informs treatment decisions\n\n"
            "5. Procedure Explanation\n"
            "   - What will be done (assess, clean, dress wound)\n"
            "   - Why it's needed\n"
            "   - Why critical: Informed consent, patient cooperation\n\n"
            "6. Patient Comfort Check\n"
            "   - Basic needs before starting\n"
            "   - Why critical: Prevents interruptions, shows patient-centered care\n\n"
            "EVALUATION RULES:\n"
            "- Base evaluation ONLY on the actual conversation transcript\n"
            "- If information was not asked about, it is NOT gathered (even if scenario contains it)\n"
            "- Do NOT evaluate communication style (tone, politeness) - that's for CommunicationAgent\n"
            "- Do NOT evaluate physical execution - that's for ClinicalAgent\n"
            "- Do NOT assume or invent student actions\n"
            "- Missing allergy assessment is ALWAYS a critical safety issue\n"
            "- Missing pain assessment is a significant gap\n"
            "- Missing identity verification is a safety concern\n\n"
            "OUTPUT FORMAT (RAW JSON ONLY):\n"
            "{\n"
            '  "agent_name": "KnowledgeAgent",\n'
            '  "step": "history",\n'
            '  "strengths": ["Specific information correctly gathered with examples..."],\n'
            '  "issues_detected": ["Specific information gaps with clinical impact..."],\n'
            '  "explanation": "Assessment of information gathering completeness and clinical reasoning...",\n'
            '  "verdict": "Appropriate" | "Partially Appropriate" | "Inappropriate",\n'
            '  "confidence": 0.9\n'
            "}\n\n"
            "VERDICT GUIDELINES:\n"
            "- Appropriate: All essential information gathered (identity, allergies, pain, medical history, procedure explained)\n"
            "- Partially Appropriate: Some essential information gathered but missing critical elements (e.g., allergies, pain)\n"
            "- Inappropriate: Multiple critical information gaps OR failed to gather allergy information\n"
        )

        user_prompt = (
            f"CONVERSATION TRANSCRIPT:\n"
            f"{student_input}\n\n"
            f"AVAILABLE PATIENT INFORMATION (for comparison):\n"
            f"Name: {scenario_metadata.get('patient_history', {}).get('name', 'Unknown')}\n"
            f"Age: {scenario_metadata.get('patient_history', {}).get('age', 'Unknown')}\n"
            f"Address: {scenario_metadata.get('patient_history', {}).get('address', 'Unknown')}\n"
            f"Medical History: {', '.join(scenario_metadata.get('patient_history', {}).get('medical_history', [])) or 'None'}\n"
            f"Allergies: {', '.join(scenario_metadata.get('patient_history', {}).get('allergies', [])) or 'None'}\n"
            f"Current Medications: {', '.join(scenario_metadata.get('patient_history', {}).get('current_medications', [])) or 'None'}\n"
            f"Surgery: {scenario_metadata.get('patient_history', {}).get('surgery_details', {}).get('procedure', 'Unknown')}\n"
            f"Pain Level: {scenario_metadata.get('patient_history', {}).get('pain_level', {}).get('description', 'Unknown')}\n"
            f"Wound Type: {scenario_metadata.get('wound_details', {}).get('wound_type', 'Unknown')}\n"
            f"Wound Location: {scenario_metadata.get('wound_details', {}).get('location', 'Unknown')}\n\n"
            f"REFERENCE GUIDELINES:\n"
            f"{rag_response}\n\n"
            "Evaluate what information the student actually gathered from the conversation.\n"
            "Remember: If the student didn't ask about it, they didn't gather it."
        )

        raw_response = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )

        try:
            clean_json = raw_response.replace("```json", "").replace("```", "").strip()
            response_data = json.loads(clean_json)
            
            response_data["step"] = current_step
            response_data["agent_name"] = "KnowledgeAgent"

            return EvaluatorResponse(**response_data)

        except (json.JSONDecodeError, ValueError, ValidationError) as e:
            print(f"KnowledgeAgent Parsing Failed: {e}")
            return EvaluatorResponse(
                agent_name="KnowledgeAgent",
                step=current_step,
                strengths=[],
                issues_detected=["Error parsing evaluator response"],
                explanation=f"Failed to parse LLM output. Raw: {raw_response[:50]}...",
                verdict="Inappropriate",
                confidence=0.0
            )
