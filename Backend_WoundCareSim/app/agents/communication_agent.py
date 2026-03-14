import ast
import json
import logging
import re

from pydantic import ValidationError

from app.agents.agent_base import BaseAgent
from app.utils.schema import EvaluatorResponse

logger = logging.getLogger(__name__)


class CommunicationAgent(BaseAgent):

    # Minimum number of distinct student turns required for 'Appropriate'
    MIN_TURNS_APPROPRIATE = 4
    # Minimum turns for 'Partially Appropriate'
    MIN_TURNS_PARTIAL = 2

    def __init__(self):
        super().__init__()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        current_step: str,
        student_input: str,
        scenario_metadata: dict,
        rag_response: str,
        clinical_context: dict = None,
    ) -> EvaluatorResponse:

        clinical_context = clinical_context or {}
        risk_factors     = clinical_context.get("risk_factors", [])
        has_diabetes     = "diabetes" in risk_factors

        # ── Guard: no input ──────────────────────────────────────────
        if not student_input or not student_input.strip():
            return EvaluatorResponse(
                agent_name="CommunicationAgent",
                step=current_step,
                strengths=[],
                issues_detected=["No patient communication detected"],
                explanation="The student did not engage with the patient at all.",
                verdict="Inappropriate",
                confidence=1.0,
            )

        # ── Guard: no student turns ──────────────────────────────────
        student_lines = [
            line for line in student_input.splitlines()
            if line.strip().lower().startswith("student:")
        ]
        if not student_lines:
            return EvaluatorResponse(
                agent_name="CommunicationAgent",
                step=current_step,
                strengths=[],
                issues_detected=["Student did not ask any questions or communicate with the patient"],
                explanation=(
                    "No student turns were found in the transcript. "
                    "The student did not communicate with the patient during history taking."
                ),
                verdict="Inappropriate",
                confidence=1.0,
            )

        # ── Build prompts ────────────────────────────────────────────
        system_prompt = self._build_system_prompt(
            rag_response=rag_response,
            has_diabetes=has_diabetes,
            clinical_context=clinical_context,
            num_student_turns=len(student_lines),
        )
        user_prompt = self._build_user_prompt(student_input)

        raw_response = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        return self._parse_response(raw_response, current_step, student_input)

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_system_prompt(
        self,
        rag_response: str,
        has_diabetes: bool,
        clinical_context: dict,
        num_student_turns: int,
    ) -> str:

        clinical_note = ""
        if has_diabetes:
            clinical_note = (
                "\nPATIENT CLINICAL CONTEXT:\n"
                "This patient has Type 2 Diabetes Mellitus. When evaluating communication,\n"
                "consider whether the student showed appropriate sensitivity to the patient's\n"
                "condition — for example, acknowledging that wound healing may be more complex,\n"
                "or being especially reassuring given the elevated clinical risk.\n"
            )

        return (
            "You are a strict nursing education evaluator assessing a student nurse's\n"
            "communication quality during patient history taking.\n\n"

            "REFERENCE COMMUNICATION GUIDELINES:\n"
            "----------------------------------------\n"
            f"{rag_response}\n"
            "----------------------------------------\n\n"

            "YOUR ROLE:\n"
            "Evaluate HOW the student communicated — not WHAT clinical topics they covered.\n"
            "Clinical topic coverage is assessed by a separate Knowledge Agent.\n"
            "Do not reward or penalise the student for which questions they asked;\n"
            "only evaluate the quality and manner of their communication.\n\n"

            "EVALUATION DIMENSIONS — assess all six:\n\n"

            "1. PROFESSIONAL OPENING\n"
            "   Did the student greet the patient AND introduce themselves before asking\n"
            "   questions? A student who launches straight into questions without any\n"
            "   greeting or introduction has failed this dimension.\n\n"

            "2. LANGUAGE APPROPRIATENESS\n"
            "   Did the student use plain language the patient would understand?\n"
            "   Medical jargon directed at a layperson is a failure. Informal or\n"
            "   dismissive language is also a failure.\n\n"

            "3. ACKNOWLEDGEMENT OF PATIENT RESPONSES\n"
            "   Did the student respond to what the patient said before moving on?\n"
            "   A transcript that looks like a questionnaire — question, answer,\n"
            "   question, answer with no bridging — indicates poor communication\n"
            "   even if the right topics were covered.\n\n"

            "4. EMPATHY AND RAPPORT\n"
            "   Did the student show warmth and awareness that they are speaking to\n"
            "   a person who may be anxious or in discomfort? Simple phrases like\n"
            "   'I understand', 'thank you for telling me that', or 'I will be gentle'\n"
            "   count. Their complete absence in a conversation about a surgical wound\n"
            "   is a notable gap.\n\n"

            "5. QUESTIONING TECHNIQUE\n"
            "   Did the student use open-ended questions where appropriate?\n"
            "   Did they follow up on concerning answers, or move on mechanically?\n"
            "   Closed yes/no questions for every topic is a technique failure.\n\n"

            "6. CLOSING\n"
            "   Did the student explain what would happen next, or thank the patient?\n"
            "   An abrupt end to the conversation without any closing remark is a\n"
            "   professionalism gap.\n\n"

            f"{clinical_note}\n"

            "VERDICT CRITERIA — apply these strictly:\n\n"

            "Return 'Appropriate' ONLY IF ALL of the following are true:\n"
            f"  - The student had at least {self.MIN_TURNS_APPROPRIATE} exchanges with the patient\n"
            "  - The student greeted the patient AND introduced themselves\n"
            "  - The student used respectful, plain language throughout\n"
            "  - The student acknowledged patient responses before moving on\n"
            "  - The student showed at least one clear moment of empathy or reassurance\n"
            "  - No rude, dismissive, or inappropriate language was used\n\n"

            "Return 'Partially Appropriate' if ANY of the following are true:\n"
            "  - The student asked questions but did not greet or introduce themselves\n"
            "  - The student ignored or did not acknowledge patient answers\n"
            f"  - The student had fewer than {self.MIN_TURNS_APPROPRIATE} exchanges\n"
            "  - The tone was overly clinical with no warmth or empathy shown\n"
            "  - The conversation was mechanical and questionnaire-like\n"
            "  - The student did not provide a closing remark\n\n"

            "Return 'Inappropriate' if ANY of the following are true:\n"
            "  - The student used rude, dismissive, or disrespectful language\n"
            f"  - The student had fewer than {self.MIN_TURNS_PARTIAL} exchanges\n"
            "  - The student showed no attempt at professional communication\n"
            "  - The student gave the patient incorrect information\n\n"

            "CRITICAL INSTRUCTIONS:\n"
            "  - Be critical and objective. Do not give the benefit of the doubt.\n"
            "  - A polite but very short conversation is NOT 'Appropriate'.\n"
            "    It is at best 'Partially Appropriate'.\n"
            "  - Do not reward effort or intention — only evaluate what actually\n"
            "    happened in the transcript.\n"
            "  - If you are unsure between 'Appropriate' and 'Partially Appropriate',\n"
            "    choose 'Partially Appropriate'.\n"
            "  - The issues_detected list must NEVER be empty. Even a good communicator\n"
            "    has at least one area for growth. Identify the weakest point.\n"
            "  - Do not evaluate clinical knowledge coverage. That is not your role.\n\n"

            "Return ONLY valid JSON. No markdown. No commentary. No explanation outside the JSON.\n"
            "Use this exact schema:\n"
            "{\n"
            '  "strengths": ["specific observed strength"],\n'
            '  "issues_detected": ["specific observed issue — must have at least one"],\n'
            '  "explanation": "2-3 sentence summary referencing specific transcript evidence",\n'
            '  "verdict": "Appropriate" | "Partially Appropriate" | "Inappropriate",\n'
            '  "confidence": 0.85\n'
            "}"
        )

    def _build_user_prompt(self, student_input: str) -> str:
        return (
            "Critically evaluate the student's communication quality using the verdict\n"
            "criteria above. Be strict — partial or minimal engagement must not receive\n"
            "'Appropriate'. Reference specific lines from the transcript in your explanation.\n\n"
            "TRANSCRIPT:\n"
            "----------------------------------------\n"
            f"{student_input}\n"
            "----------------------------------------"
        )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(
        self,
        raw_response: str,
        current_step: str,
        student_input: str,
    ) -> EvaluatorResponse:
        for idx, candidate in enumerate(self._json_candidates(raw_response), start=1):
            try:
                data = self._load_json_lenient(candidate)
                return self._build_response(data, current_step)
            except (json.JSONDecodeError, ValidationError, SyntaxError, ValueError) as exc:
                logger.warning(f"CommunicationAgent parse attempt {idx} failed: {exc}")

        logger.error(
            "CommunicationAgent failed to parse LLM output.\n"
            f"Raw response:\n{raw_response}"
        )
        return self._heuristic_fallback(current_step, student_input)

    def _json_candidates(self, raw: str) -> list[str]:
        stripped = raw.strip()
        candidates = []

        # Strip markdown fences
        fenced = re.sub(r"```json\s*", "", stripped, flags=re.IGNORECASE)
        fenced = re.sub(r"```\s*", "", fenced).strip()
        if fenced:
            candidates.append(fenced)

        # Extract first {...} block
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if match:
            extracted = match.group().strip()
            if extracted not in candidates:
                candidates.append(extracted)

        # Trailing comma repair
        repaired = re.sub(r",(\s*[}\]])", r"\1", fenced)
        if repaired and repaired not in candidates:
            candidates.append(repaired.strip())

        return candidates

    def _load_json_lenient(self, candidate: str) -> dict:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            py = re.sub(r"\btrue\b",  "True",  candidate, flags=re.IGNORECASE)
            py = re.sub(r"\bfalse\b", "False", py,        flags=re.IGNORECASE)
            py = re.sub(r"\bnull\b",  "None",  py,        flags=re.IGNORECASE)
            loaded = ast.literal_eval(py)
            if not isinstance(loaded, dict):
                raise ValueError("Parsed value is not a dict")
            return loaded

    def _build_response(self, data: dict, current_step: str) -> EvaluatorResponse:
        data["step"]       = current_step
        data["agent_name"] = "CommunicationAgent"

        if not isinstance(data.get("strengths"), list):
            data["strengths"] = []
        if not isinstance(data.get("issues_detected"), list):
            data["issues_detected"] = []

        # Enforce non-empty issues_detected — always at least one entry
        if not data["issues_detected"]:
            data["issues_detected"] = [
                "No specific improvement areas were identified; consider asking more open-ended questions"
            ]

        valid_verdicts = {"Appropriate", "Partially Appropriate", "Inappropriate"}
        if data.get("verdict") not in valid_verdicts:
            logger.warning(
                f"CommunicationAgent invalid verdict: '{data.get('verdict')}'. "
                "Defaulting to 'Partially Appropriate'."
            )
            # Default to Partially Appropriate (not Inappropriate) to avoid
            # unfairly penalising when the model simply returned a malformed verdict.
            data["verdict"] = "Partially Appropriate"

        try:
            data["confidence"] = round(
                max(0.0, min(1.0, float(data.get("confidence", 0.0)))), 2
            )
        except (TypeError, ValueError):
            data["confidence"] = 0.0

        return EvaluatorResponse(**data)

    # ------------------------------------------------------------------
    # Heuristic fallback (no LLM parsing)
    # ------------------------------------------------------------------

    def _heuristic_fallback(self, current_step: str, student_input: str) -> EvaluatorResponse:
        """
        Deterministic keyword-based fallback used only when LLM output
        cannot be parsed at all. Intentionally conservative.
        """
        student_lines = [
            line.split(":", 1)[1].strip() if ":" in line else line.strip()
            for line in student_input.splitlines()
            if line.strip().lower().startswith("student:")
        ]
        joined = " ".join(student_lines).lower()
        num_turns = len(student_lines)

        greeting_markers     = ["hello", "good morning", "good afternoon", "good evening", "hi "]
        intro_markers        = ["i am your nurse", "i am your student nurse",
                                "i am the nursing student", "i am here to",
                                "my name is", "i will be"]
        rude_markers         = ["answer quickly", "i do not have time", "get this over with",
                                "listen carefully", "state your", "or not"]
        empathy_markers      = ["how are you feeling", "i understand", "thank you for",
                                "i am sorry", "comfort", "that must be", "i will be gentle"]
        open_question_tokens = ["tell me", "can you describe", "how would you", "what is",
                                "how has", "could you explain"]
        closing_markers      = ["thank you", "we will now", "next we will", "i will now",
                                "that is all for now"]

        has_greeting     = any(m in joined for m in greeting_markers)
        has_intro        = any(m in joined for m in intro_markers)
        has_rude         = any(m in joined for m in rude_markers)
        has_empathy      = any(m in joined for m in empathy_markers)
        has_open_q       = any(m in joined for m in open_question_tokens)
        has_closing      = any(m in joined for m in closing_markers)
        asks_questions   = ("?" in student_input or
                            any(t in joined for t in ["do you", "can you", "could you",
                                                      "have you", "how much", "what is your"]))

        strengths = []
        issues    = []

        if has_greeting and has_intro:
            strengths.append("Greeted the patient and introduced themselves professionally")
        elif has_greeting:
            strengths.append("Greeted the patient")
            issues.append("Self-introduction was missing or incomplete")
        else:
            issues.append("No greeting or professional introduction at the start of the consultation")

        if asks_questions:
            strengths.append("Engaged the patient with direct questions")
        else:
            issues.append("Minimal or no questioning of the patient observed")

        if has_open_q:
            strengths.append("Used open-ended questioning technique")
        else:
            issues.append("Questions were predominantly closed or yes/no in format")

        if has_empathy:
            strengths.append("Showed empathy or reassurance toward the patient")
        else:
            issues.append("No empathetic language or reassurance was observed")

        if has_closing:
            strengths.append("Provided a professional closing remark")
        else:
            issues.append("No closing remark or explanation of next steps was given")

        # Verdict
        if has_rude:
            issues.insert(0, "Tone included rude, dismissive, or pressuring language")
            verdict = "Inappropriate"
        elif num_turns < self.MIN_TURNS_PARTIAL:
            issues.insert(0, f"Very limited engagement — only {num_turns} student turn(s) recorded")
            verdict = "Inappropriate"
        elif (has_greeting and has_intro and has_empathy
              and asks_questions and num_turns >= self.MIN_TURNS_APPROPRIATE):
            verdict = "Appropriate"
        elif asks_questions or has_greeting:
            verdict = "Partially Appropriate"
        else:
            verdict = "Inappropriate"

        # Ensure at least one issue is always present
        if not issues:
            issues.append("Consider using more open-ended questions and explicitly acknowledging patient responses")

        return EvaluatorResponse(
            agent_name="CommunicationAgent",
            step=current_step,
            strengths=strengths[:4],
            issues_detected=issues[:4],
            explanation=(
                "Heuristic fallback was used because the LLM evaluator response could not be parsed. "
                "Verdict was determined from greeting, introduction, empathy, questioning technique, "
                "and closing markers in the transcript."
            ),
            verdict=verdict,
            confidence=0.35,
        )
