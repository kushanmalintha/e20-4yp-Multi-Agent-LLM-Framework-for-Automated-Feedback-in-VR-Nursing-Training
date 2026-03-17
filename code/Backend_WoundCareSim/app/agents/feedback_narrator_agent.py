from typing import List, Dict, Any, Optional
import json

from app.agents.agent_base import BaseAgent
from app.utils.narrated_feedback_schema import NarratedFeedback


class FeedbackNarratorAgent(BaseAgent):
    """
    Converts raw agent feedback into student-friendly narrated paragraphs.
    
    Purpose:
    - Transform technical agent outputs into encouraging, clear feedback
    - Maintain educational tone (formative, not punitive)
    - Provide actionable guidance for improvement
    """

    def __init__(self):
        super().__init__()

    async def narrate(
        self,
        raw_feedback: List[Dict[str, Any]],
        step: str,
        score: Optional[int] = None,
        clinical_context: dict = None,
    ) -> NarratedFeedback:
        """
        Generate narrated feedback paragraph from raw agent outputs.
        
        Args:
            raw_feedback: List of agent feedback items
            step: Current procedure step
            score: Step quality score as a percentage (0-100), optional
            
        Returns:
            NarratedFeedback with single student-facing paragraph
        """

        system_prompt = self._build_system_prompt(step, clinical_context=clinical_context)
        user_prompt = self._build_user_prompt(raw_feedback, step, score=score)

        output_text = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3
        )

        return self._parse_output(output_text, raw_feedback, step)

    # --------------------------------------------------
    # Prompt construction
    # --------------------------------------------------

    def _build_system_prompt(self, step: str, clinical_context: dict = None) -> str:
        """Build system prompt with step-specific guidance."""
        clinical_context = clinical_context or {}
        risk_factors = clinical_context.get("risk_factors", [])
        healing_risk = clinical_context.get("healing_risk", "normal")
        infection_risk = clinical_context.get("infection_risk", "normal")
        has_diabetes = "diabetes" in risk_factors

        clinical_context_block = ""
        if has_diabetes:
            clinical_context_block = f"""
PATIENT CLINICAL CONTEXT:
Risk Factors: Type 2 Diabetes Mellitus
Healing Risk: {healing_risk.replace("_", " ").title()}
Infection Risk: {infection_risk.replace("_", " ").title()}

When generating feedback:
- Explain how diabetes increases infection risk and delays wound healing
- Highlight why thorough history taking is especially important for this patient
- If the student asked about diabetic risk factors, acknowledge this positively
- If the student did not ask about diabetic risk factors, mention this as an
  important area for improvement given the patient's condition
"""
        
        step_context = {
            "history": "patient communication and information gathering",
            "assessment": "wound assessment through multiple-choice questions",
            "cleaning_and_dressing": "preparation for wound cleaning and dressing"
        }
        
        context = step_context.get(step, "clinical procedure")
        
        return f"""
You are a nursing education tutor providing feedback to students.

Your task is to convert technical evaluation feedback into ONE clear, supportive paragraph.

CONTEXT:
- Step: {step} ({context})
- Formative nursing education (learning-focused, not punitive)
- Student is in training

RULES:
1. Write ONE cohesive paragraph (3-5 sentences)
2. Start with positive acknowledgment if strengths exist
3. Mention areas for improvement constructively
4. Naturally include the step quality score if provided (e.g. "You scored 72 out of 100")
5. End with encouraging, forward-looking statement
6. Use supportive, professional tone
7. Do NOT add new medical advice
8. Do NOT contradict the feedback provided
9. Be specific but concise

{clinical_context_block}STRUCTURE:
- Opening: Acknowledge what student did well (if applicable)
- Middle: Mention key areas for improvement (if applicable)
- Closing: Encouraging statement about learning/next steps

OUTPUT FORMAT:
Raw JSON only (no markdown, no extra text):
{{
  "speaker": "system",
  "message_text": "Your narrated paragraph here..."
}}

TONE EXAMPLES:
- Good: "You demonstrated strong communication skills by introducing yourself and asking about allergies. To improve further, consider gathering more detailed pain information and verifying the patient's medical history. Keep practicing these essential history-taking techniques."
  
- Avoid: "You failed to ask proper questions. Multiple critical errors were detected. This performance is unacceptable."
"""

    def _build_user_prompt(self, raw_feedback: List[Dict[str, Any]], step: str, score: Optional[int] = None) -> str:
        """Build user prompt with raw feedback to narrate."""
        
        # Categorize feedback by agent/category
        communication_feedback = []
        knowledge_feedback = []
        clinical_feedback = []
        
        for item in raw_feedback:
            category = item.get("category", "")
            text = item.get("text", "")
            
            if category == "communication":
                communication_feedback.append(text)
            elif category == "knowledge":
                knowledge_feedback.append(text)
            elif category == "clinical":
                clinical_feedback.append(text)
        
        prompt = f"STEP: {step}\n\n"

        if score is not None:
            prompt += f"STEP QUALITY SCORE: {score}/100\n\n"

        prompt += "RAW FEEDBACK TO NARRATE:\n\n"
        
        if communication_feedback:
            prompt += "COMMUNICATION EVALUATION:\n"
            prompt += "\n".join(communication_feedback) + "\n\n"
        
        if knowledge_feedback:
            prompt += "KNOWLEDGE EVALUATION:\n"
            prompt += "\n".join(knowledge_feedback) + "\n\n"
        
        if clinical_feedback:
            prompt += "CLINICAL EVALUATION:\n"
            prompt += "\n".join(clinical_feedback) + "\n\n"
        
        prompt += (
            "Convert this feedback into ONE supportive paragraph that:\n"
            "1. Acknowledges strengths first (if any)\n"
            "2. Mentions areas for improvement constructively\n"
            "3. Naturally includes the step quality score (e.g. 'You achieved a score of X out of 100')\n"
            "4. Ends with encouragement\n\n"
            "Keep it concise, specific, and educational."
        )
        
        return prompt

    # --------------------------------------------------
    # Output parsing with safe fallback
    # --------------------------------------------------

    def _parse_output(
        self,
        output_text: str,
        raw_feedback: List[Dict[str, Any]],
        step: str
    ) -> NarratedFeedback:
        """Parse LLM output into NarratedFeedback, with fallback."""

        try:
            # Try to parse JSON
            clean_json = output_text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_json)

            return NarratedFeedback(
                speaker=parsed.get("speaker", "system"),
                step=step,
                message_text=parsed["message_text"]
            )

        except Exception as e:
            print(f"⚠️  Narration parsing failed: {e}")
            
            # Fallback: Simple concatenation
            combined_text = " ".join(
                item.get("text", "") for item in raw_feedback
            )
            
            # If combined text is too long, truncate intelligently
            if len(combined_text) > 500:
                combined_text = combined_text[:500] + "... Please review detailed feedback for more information."

            return NarratedFeedback(
                speaker="system",
                step=step,
                message_text=combined_text if combined_text else "Feedback evaluation complete."
            )
