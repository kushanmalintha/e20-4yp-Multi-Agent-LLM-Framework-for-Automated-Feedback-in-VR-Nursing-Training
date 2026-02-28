import json
import re
import logging
from pydantic import ValidationError
from app.agents.agent_base import BaseAgent
from app.utils.schema import EvaluatorResponse

logger = logging.getLogger(__name__)


class CommunicationAgent(BaseAgent):
    """
    Evaluates communication skills during history taking.
    Now grounded with RAG guideline context.
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

        if not student_input or student_input.strip() == "":
            return EvaluatorResponse(
                agent_name="CommunicationAgent",
                step=current_step,
                strengths=[],
                issues_detected=["No patient communication detected"],
                explanation="The student did not engage with the patient.",
                verdict="Inappropriate",
                confidence=0.0
            )

        system_prompt = (
            "You are a nursing communication evaluator for history-taking.\n\n"
            "REFERENCE COMMUNICATION GUIDELINES:\n"
            "═══════════════════════════════════════════════════════════════\n"
            f"{rag_response}\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            "Evaluate ONLY communication behavior:\n"
            "- Professional introduction\n"
            "- Respectful tone\n"
            "- Empathy and listening\n"
            "- Patient-centered approach\n\n"
            "Do NOT evaluate clinical knowledge.\n\n"
            "You MUST return a valid JSON object only. No markdown, no explanation, "
            "no code fences. Nothing before or after the JSON.\n\n"
            "Required JSON format:\n"
            "{\n"
            '  "strengths": ["..."],\n'
            '  "issues_detected": ["..."],\n'
            '  "explanation": "...",\n'
            '  "verdict": "Appropriate" | "Partially Appropriate" | "Inappropriate",\n'
            '  "confidence": 0.0 to 1.0\n'
            "}"
        )

        user_prompt = (
            "TRANSCRIPT:\n"
            "═══════════════════════════════════════════════════════════════\n"
            f"{student_input}\n"
            "═══════════════════════════════════════════════════════════════"
        )

        raw_response = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )

        return self._parse_response(raw_response, current_step)

    def _parse_response(self, raw_response: str, current_step: str) -> EvaluatorResponse:
        """
        Robustly extract and parse JSON from the LLM response.
        Handles cases where the LLM wraps JSON in markdown, adds preamble
        text, or returns slightly malformed output.
        """
        # Step 1: Try extracting JSON object using regex (most robust)
        # This handles markdown fences, preamble text, trailing text, etc.
        try:
            match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if match:
                clean_json = match.group()
                response_data = json.loads(clean_json)
                return self._build_response(response_data, current_step)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"CommunicationAgent regex extraction failed: {e}")

        # Step 2: Fallback — strip markdown fences and try again
        try:
            clean_json = raw_response
            clean_json = re.sub(r'```json\s*', '', clean_json)
            clean_json = re.sub(r'```\s*', '', clean_json)
            clean_json = clean_json.strip()
            response_data = json.loads(clean_json)
            return self._build_response(response_data, current_step)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"CommunicationAgent stripped fallback failed: {e}")

        # Step 3: Hard fallback — log the raw response for debugging
        logger.error(
            f"CommunicationAgent failed to parse LLM output.\n"
            f"Raw response was:\n{raw_response}"
        )
        return EvaluatorResponse(
            agent_name="CommunicationAgent",
            step=current_step,
            strengths=[],
            issues_detected=["Failed to parse evaluator output"],
            explanation="Evaluation system error.",
            verdict="Inappropriate",
            confidence=0.0
        )

    def _build_response(self, response_data: dict, current_step: str) -> EvaluatorResponse:
        """
        Validate and normalise parsed JSON into an EvaluatorResponse.
        """
        response_data["step"] = current_step
        response_data["agent_name"] = "CommunicationAgent"

        # Ensure strengths and issues_detected are lists
        if not isinstance(response_data.get("strengths"), list):
            response_data["strengths"] = []
        if not isinstance(response_data.get("issues_detected"), list):
            response_data["issues_detected"] = []

        # Validate verdict
        valid_verdicts = ["Appropriate", "Partially Appropriate", "Inappropriate"]
        if response_data.get("verdict") not in valid_verdicts:
            logger.warning(
                f"CommunicationAgent received invalid verdict: "
                f"'{response_data.get('verdict')}'. Defaulting to 'Inappropriate'."
            )
            response_data["verdict"] = "Inappropriate"

        # Clamp confidence to [0.0, 1.0]
        try:
            confidence = float(response_data.get("confidence", 0.0))
            response_data["confidence"] = round(max(0.0, min(1.0, confidence)), 2)
        except (TypeError, ValueError):
            response_data["confidence"] = 0.0

        return EvaluatorResponse(**response_data)
