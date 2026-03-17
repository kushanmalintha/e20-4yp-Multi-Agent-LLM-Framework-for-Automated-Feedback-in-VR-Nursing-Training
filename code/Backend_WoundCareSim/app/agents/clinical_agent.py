import logging
from app.agents.agent_base import BaseAgent

logger = logging.getLogger(__name__)


class ClinicalAgent(BaseAgent):
    """
    Clinical Agent — deterministic prerequisite validation + LLM educational explanation.

    Validation (pass/fail, missing actions) is 100% deterministic using the
    hardcoded PREREQUISITE_MAP. No LLM is involved in this decision.

    LLM is used in exactly two places:
      1. Missing prerequisite explanation — when a student skips steps,
         the LLM generates a short clinically grounded reason WHY those
         prerequisites matter, using the RAG guideline text as context.
         The verdict is already locked before the LLM is called.

      2. Step completion summary — called once when the student finishes
         the cleaning step. The LLM narrates what the student did and
         what they missed, based purely on recorded action_events facts.
    """

    PREREQUISITE_MAP: dict[str, list[str]] = {
        "action_initial_hand_hygiene": [],
        "action_clean_trolley": [
            "action_initial_hand_hygiene"
        ],
        "action_hand_hygiene_after_cleaning": [
            "action_initial_hand_hygiene",
            "action_clean_trolley"
        ],
        "action_select_solution": [
            "action_initial_hand_hygiene",
            "action_clean_trolley",
            "action_hand_hygiene_after_cleaning"
        ],
        "action_verify_solution": [
            "action_initial_hand_hygiene",
            "action_clean_trolley",
            "action_hand_hygiene_after_cleaning",
            "action_select_solution"
        ],
        "action_select_dressing": [
            "action_initial_hand_hygiene",
            "action_clean_trolley",
            "action_hand_hygiene_after_cleaning",
            "action_select_solution",
            "action_verify_solution"
        ],
        "action_verify_dressing": [
            "action_initial_hand_hygiene",
            "action_clean_trolley",
            "action_hand_hygiene_after_cleaning",
            "action_select_solution",
            "action_verify_solution",
            "action_select_dressing"
        ],
        "action_arrange_materials": [
            "action_initial_hand_hygiene",
            "action_clean_trolley",
            "action_hand_hygiene_after_cleaning",
            "action_select_solution",
            "action_verify_solution",
            "action_select_dressing",
            "action_verify_dressing"
        ],
        "action_bring_trolley": [
            "action_initial_hand_hygiene",
            "action_clean_trolley",
            "action_hand_hygiene_after_cleaning",
            "action_select_solution",
            "action_verify_solution",
            "action_select_dressing",
            "action_verify_dressing",
            "action_arrange_materials"
        ],
    }

    # Human-readable names for action keys
    ACTION_NAMES: dict[str, str] = {
        "action_initial_hand_hygiene":       "Initial Hand Hygiene",
        "action_clean_trolley":              "Clean the Dressing Trolley",
        "action_hand_hygiene_after_cleaning":"Hand Hygiene After Trolley Cleaning",
        "action_select_solution":            "Select Prescribed Cleaning Solution",
        "action_verify_solution":            "Verify Cleaning Solution with Staff Nurse",
        "action_select_dressing":            "Select Dressing Materials",
        "action_verify_dressing":            "Verify Sterile Dressing Packet with Staff Nurse",
        "action_arrange_materials":          "Arrange Solutions and Materials on Trolley",
        "action_bring_trolley":              "Bring Prepared Trolley to Patient Area",
    }

    def _name(self, action_type: str) -> str:
        return self.ACTION_NAMES.get(
            action_type,
            action_type.replace("action_", "").replace("_", " ").title()
        )

    # ------------------------------------------------------------------
    # PUBLIC: Real-time feedback (called on every action click)
    # ------------------------------------------------------------------

    async def get_real_time_feedback(
        self,
        action_type: str,
        performed_actions: list[dict],
        rag_guidelines: str = "",
        clinical_context: dict = None,
        **_: object,
    ) -> dict:
        """
        Deterministic prerequisite check + LLM explanation when missing.

        Pass/fail is decided by the PREREQUISITE_MAP alone.
        LLM is only called when prerequisites are missing, to explain WHY.
        rag_guidelines provides clinical context for that explanation.
        """

        completed = [a["action_type"] for a in performed_actions]
        prerequisites = self.PREREQUISITE_MAP.get(action_type, [])
        missing = [p for p in prerequisites if p not in completed]
        action_name = self._name(action_type)

        # ----------------------------------------------------------
        # CASE 1: All prerequisites met — simple success message
        # No LLM needed.
        # ----------------------------------------------------------
        if not missing:
            return {
                "status": "complete",
                "message": f"{action_name}: Done correctly.",
                "missing_actions": [],
                "can_proceed": True,
                "action_type": action_type,
                "total_actions_so_far": len(performed_actions) + 1,
            }

        # ----------------------------------------------------------
        # CASE 2: Prerequisites missing — LLM explains WHY
        # Verdict is already locked (missing_prerequisites).
        # LLM only generates the clinical reasoning explanation.
        # ----------------------------------------------------------
        missing_names = [self._name(m) for m in missing]
        explanation = await self._explain_missing_prerequisites(
            action_name=action_name,
            missing_names=missing_names,
            rag_guidelines=rag_guidelines,
            clinical_context=clinical_context or {},
        )

        return {
            "status": "missing_prerequisites",
            "message": explanation,
            "missing_actions": missing,
            "can_proceed": False,
            "action_type": action_type,
            "total_actions_so_far": len(performed_actions) + 1,
        }

    # ------------------------------------------------------------------
    # PUBLIC: Step completion summary (called once when step ends)
    # ------------------------------------------------------------------

    async def generate_step_summary(
        self,
        action_events: list[dict],
        rag_guidelines: str = "",
        clinical_context: dict = None,
    ) -> str:
        """
        LLM narrates what the student did and what they missed.
        Called once when the student finishes the cleaning_and_dressing step.

        Input is purely the recorded action_events facts — the LLM cannot
        misreport what happened because it only describes what is in the log.
        """

        all_actions = list(self.PREREQUISITE_MAP.keys())
        performed = [e["action_type"] for e in action_events]
        skipped = [a for a in all_actions if a not in performed]

        performed_names = [self._name(a) for a in performed]
        skipped_names = [self._name(a) for a in skipped]

        clinical_context = clinical_context or {}
        risk_factors = clinical_context.get("risk_factors", [])
        has_diabetes = "diabetes" in risk_factors

        diabetes_note = ""
        if has_diabetes:
            diabetes_note = (
                "\nPATIENT CONTEXT: This patient has Type 2 Diabetes. "
                "Where relevant, explain how missed actions carry higher risk "
                "for diabetic patients due to impaired healing and infection susceptibility."
            )

        system_prompt = (
            "You are a nursing clinical educator providing end-of-step feedback.\n\n"
            "You are given a factual log of what a student did and did not do "
            "during the wound cleaning and dressing PREPARATION step.\n\n"
            "Write a concise 3-4 sentence summary that:\n"
            "- Acknowledges what the student completed correctly\n"
            "- Clearly states any skipped or missing actions\n"
            "- Explains the patient safety implication of any missed actions\n"
            "- Uses a professional but encouraging tone\n\n"
            "Base your explanation on the clinical guidelines provided.\n"
            "Do NOT invent actions not in the log. Do NOT evaluate clinical judgment.\n"
            "Keep it brief and spoken-friendly."
            f"{diabetes_note}"
        )

        performed_str = (
            "\n".join(f"  - {n}" for n in performed_names)
            if performed_names else "  (none)"
        )
        skipped_str = (
            "\n".join(f"  - {n}" for n in skipped_names)
            if skipped_names else "  (none — all actions completed)"
        )

        user_prompt = (
            f"CLINICAL GUIDELINES:\n{rag_guidelines}\n\n"
            f"ACTIONS COMPLETED:\n{performed_str}\n\n"
            f"ACTIONS SKIPPED:\n{skipped_str}\n\n"
            "Provide the end-of-step summary."
        )

        try:
            return await self.run(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"Step summary generation failed: {e}")
            # Fallback: plain factual summary without LLM
            if skipped_names:
                return (
                    f"You completed {len(performed_names)} of {len(all_actions)} "
                    f"preparation actions. Skipped: {', '.join(skipped_names)}."
                )
            return (
                f"Well done — you completed all {len(all_actions)} "
                "preparation actions correctly."
            )

    # ------------------------------------------------------------------
    # PRIVATE: LLM explanation for missing prerequisites
    # ------------------------------------------------------------------

    async def _explain_missing_prerequisites(
        self,
        action_name: str,
        missing_names: list[str],
        rag_guidelines: str,
        clinical_context: dict = None,
    ) -> str:
        """
        Generate a short clinical explanation of WHY the missing steps matter.
        Called only when prerequisites are missing — verdict is already locked.
        """

        clinical_context = clinical_context or {}
        risk_factors = clinical_context.get("risk_factors", [])
        has_diabetes = "diabetes" in risk_factors

        patient_context_note = ""
        if has_diabetes:
            patient_context_note = (
                "\nPATIENT CONTEXT: This patient has Type 2 Diabetes Mellitus. "
                "Diabetic patients have impaired immune response and delayed wound healing. "
                "Explain why the missing step is especially critical for this patient's safety."
            )

        system_prompt = (
            "You are a nursing clinical educator giving real-time feedback.\n\n"
            "A student attempted an action before completing required prerequisites.\n"
            "The verdict is already determined — you are only explaining WHY "
            "the missing steps are clinically important.\n\n"
            f"{patient_context_note}\n\n"
            "Rules:\n"
            "- Start by stating what is missing: 'Before [action], you must first: [missing steps].'\n"
            "- Then give ONE brief sentence explaining the patient safety reason.\n"
            "- Maximum 2 sentences total. Be direct and spoken-friendly.\n"
            "- Do NOT mention other actions. Do NOT give instructions for the whole step.\n"
            "- Base your reason on the clinical guidelines provided."
        )

        user_prompt = (
            f"CLINICAL GUIDELINES:\n{rag_guidelines}\n\n"
            f"Action attempted: {action_name}\n"
            f"Missing prerequisites: {', '.join(missing_names)}\n\n"
            "Provide the feedback."
        )

        try:
            return await self.run(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
            )
        except Exception as e:
            logger.error(f"Missing prerequisite explanation failed: {e}")
            # Fallback: plain template message
            return (
                f"Before {action_name}, you must first complete: "
                f"{', '.join(missing_names)}."
            )
