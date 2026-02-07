import json
import re

from pydantic import ValidationError
from app.agents.agent_base import BaseAgent
from app.utils.schema import EvaluatorResponse

class CommunicationAgent(BaseAgent):
    """
    Evaluates student communication skills during history taking.
    Focuses on: rapport building, clarity, professionalism, patient-centered approach.
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
        
        # CRITICAL: Check for empty input first
        if not student_input or student_input.strip() == "":
            return EvaluatorResponse(
                agent_name="CommunicationAgent",
                step=current_step,
                strengths=[],
                issues_detected=[
                    "No communication with patient detected",
                    "Patient history gathering is mandatory",
                    "Failed to establish rapport"
                ],
                explanation="The student did not engage in any conversation with the patient. Gathering patient history through effective communication is a critical first step in wound care. Without patient interaction, essential information about allergies, pain levels, and medical history cannot be obtained.",
                verdict="Inappropriate",
                confidence=1.0
            )
        
        system_prompt = (
            "You are a nursing communication evaluator for history-taking.\n\n"
            "ROLE: Evaluate ONLY communication skills, NOT clinical knowledge or physical actions.\n\n"
            "FOCUS ON:\n"
            "1. Introduction & Rapport\n"
            "   - Did student introduce themselves?\n"
            "   - Was the tone respectful and professional?\n"
            "   - Did student establish a welcoming environment?\n\n"
            "2. Clarity & Understanding\n"
            "   - Did student speak clearly?\n"
            "   - Did student use simple, non-technical language?\n"
            "   - Did student check patient understanding?\n\n"
            "3. Active Listening\n"
            "   - Did student acknowledge patient responses?\n"
            "   - Did student show empathy and patience?\n"
            "   - Did student follow up appropriately?\n\n"
            "4. Patient-Centered Communication\n"
            "   - Did student explain the procedure?\n"
            "   - Did student check patient comfort?\n"
            "   - Did student give patient opportunity to ask questions?\n\n"
            "EVALUATION RULES:\n"
            "- Base evaluation ONLY on the actual conversation transcript provided\n"
            "- Do NOT evaluate what questions were asked (that's knowledge evaluation)\n"
            "- Do NOT evaluate clinical accuracy (that's clinical evaluation)\n"
            "- Do NOT assume or invent student actions\n"
            "- Provide specific examples from the conversation\n\n"
            "OUTPUT FORMAT (RAW JSON ONLY):\n"
            "{\n"
            '  "agent_name": "CommunicationAgent",\n'
            '  "step": "history",\n'
            '  "strengths": ["Specific communication strengths with examples..."],\n'
            '  "issues_detected": ["Specific communication issues with examples..."],\n'
            '  "explanation": "Overall assessment of communication effectiveness...",\n'
            '  "verdict": "Appropriate" | "Partially Appropriate" | "Inappropriate",\n'
            '  "confidence": 0.8\n'
            "}\n\n"
            "VERDICT GUIDELINES:\n"
            "- Appropriate: Professional, clear, patient-centered communication throughout\n"
            "- Partially Appropriate: Some communication elements present but gaps in rapport/clarity/patient-centeredness\n"
            "- Inappropriate: Minimal communication, unprofessional tone, or failed to establish basic rapport\n"
        )

        user_prompt = (
            f"CONVERSATION TRANSCRIPT:\n"
            f"{student_input}\n\n"
            f"SCENARIO CONTEXT:\n"
            f"Patient: {scenario_metadata.get('patient_history', {}).get('name', 'Unknown')}, "
            f"{scenario_metadata.get('patient_history', {}).get('age', 'Unknown')} years old\n"
            f"Wound: {scenario_metadata.get('wound_details', {}).get('wound_type', 'Unknown')} on "
            f"{scenario_metadata.get('wound_details', {}).get('location', 'Unknown')}\n\n"
            f"REFERENCE GUIDELINES:\n"
            f"{rag_response}\n\n"
            "Evaluate the communication quality based on the actual conversation."
        )

        raw_response = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )

        try:
            clean_json = raw_response.replace("```json", "").replace("```", "").strip()
            response_data = json.loads(clean_json)
            
            # Enforce consistency
            response_data["step"] = current_step
            response_data["agent_name"] = "CommunicationAgent"

            return EvaluatorResponse(**response_data)

        except (json.JSONDecodeError, ValueError, ValidationError) as e:
            print(f"CommunicationAgent Parsing Failed: {e}")
            return EvaluatorResponse(
                agent_name="CommunicationAgent",
                step=current_step,
                strengths=[],
                issues_detected=["Error parsing evaluator response"],
                explanation=f"Failed to parse LLM output. Raw: {raw_response[:50]}...",
                verdict="Inappropriate",
                confidence=0.0
            )
