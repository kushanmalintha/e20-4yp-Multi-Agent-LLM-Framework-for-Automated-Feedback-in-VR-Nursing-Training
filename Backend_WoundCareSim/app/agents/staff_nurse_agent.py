import json
from app.agents.agent_base import BaseAgent
from app.core.step_guidance import STEP_GUIDANCE


class StaffNurseAgent(BaseAgent):
    """
    Conversational supervising nurse (GUIDANCE + VERIFICATION).

    Two modes:
    1. GUIDANCE  — explains current/next step when the student asks for help.
    2. VERIFICATION — student presents a material; nurse evaluates it fully via LLM
                      and returns a structured verdict (incomplete / rejected / approved).

    Does NOT evaluate overall performance, approve step progression, or block steps.
    """

    FINISH_KEYWORDS = [
        "finished",
        "done",
        "what next",
        "next step",
        "can i proceed",
        "ready",
        "move on",
        "complete"
    ]

    VERIFICATION_KEYWORDS = [
        "verify",
        "check",
        "confirm",
        "is this correct",
        "is this right",
        "can you check",
        "look at this",
        "solution",
        "dressing packet",
        "sterile",
        "surgical spirit",
        "dry dressing",
        "bottle",
        "packet",
        "package",
    ]

    def __init__(self):
        super().__init__()

    def _is_student_finishing(self, student_input: str) -> bool:
        student_lower = student_input.lower()
        return any(keyword in student_lower for keyword in self.FINISH_KEYWORDS)

    def _is_verification_request(self, student_input: str) -> bool:
        student_lower = student_input.lower()
        return any(keyword in student_lower for keyword in self.VERIFICATION_KEYWORDS)

    async def respond(
        self,
        student_input: str,
        current_step: str,
        next_step: str | None,
        clinical_context: dict = None,
    ) -> str:
        """
        Guidance-only response. Called when the student sends a general nurse message
        that is NOT a verification request (handled separately via verify_material_conversational).
        """
        clinical_context = clinical_context or {}
        risk_factors = clinical_context.get("risk_factors", [])
        has_diabetes = "diabetes" in risk_factors

        patient_context_note = ""
        if has_diabetes:
            patient_context_note = (
                "\nPATIENT CONTEXT: This patient has Type 2 Diabetes Mellitus. "
                "Provide guidance with awareness of higher infection risk and delayed healing. "
                "Emphasise the importance of aseptic technique and thorough preparation "
                "for this patient."
            )

        is_finishing = self._is_student_finishing(student_input)

        current_guidance = STEP_GUIDANCE.get(current_step, "")
        next_guidance = STEP_GUIDANCE.get(next_step, "") if next_step else ""

        # ================================================
        # MODE 1: VERIFICATION REDIRECT (cleaning_and_dressing)
        # ================================================
        if self._is_verification_request(student_input) and current_step == "cleaning_and_dressing":
            return (
                "I can help verify materials! Please describe the material and its "
                "condition, and I'll verify it for you."
            )

        # ================================================
        # MODE 2: NEXT STEP GUIDANCE (student signals they are done)
        # ================================================
        elif is_finishing and next_guidance:
            system_prompt = (
                "You are a supervising staff nurse guiding a nursing student.\n\n"
                "ROLE RULES:\n"
                "- Provide guidance only\n"
                "- Do NOT evaluate performance\n"
                "- Do NOT grant permission to proceed\n"
                "- The student controls step progression\n\n"
                f"{patient_context_note}\n\n"
                "TASK:\n"
                "- Student indicated they are finished with the current step\n"
                "- Briefly explain what the next step is about — its purpose and what it involves\n"
                "- Do NOT tell the student what to do or give instructions\n"
                "- Keep it to 1–2 sentences, spoken-friendly\n"
            )
            user_prompt = (
                f"CURRENT STEP: {current_step}\n"
                f"NEXT STEP: {next_step}\n"
                f"NEXT STEP GUIDANCE:\n{next_guidance}\n\n"
                f"STUDENT MESSAGE:\n{student_input}\n"
            )

        # ================================================
        # MODE 3: CURRENT STEP GUIDANCE (default)
        # ================================================
        else:
            system_prompt = (
                "You are a supervising staff nurse guiding a nursing student.\n\n"
                "ROLE RULES:\n"
                "- Provide guidance only\n"
                "- Do NOT evaluate performance\n"
                "- Do NOT grant permission to proceed\n"
                "- The student controls step progression\n\n"
                f"{patient_context_note}\n\n"
                "TASK:\n"
                "- Student is asking about the current step\n"
                "- Briefly explain what this step is about — its purpose and what it involves\n"
                "- Do NOT tell the student what to do or give instructions\n"
                "- Keep it to 1–2 sentences, spoken-friendly\n"
            )
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

    async def verify_material_conversational(
        self,
        student_message: str,
        material_type: str,
        clinical_context: dict = None,
    ) -> dict:
        """
        Evaluate the student's material verification message via LLM and return a
        structured verdict.

        The LLM nurse decides:
          - "incomplete" → student hasn't provided enough information; nurse asks naturally
          - "rejected"   → something is wrong (expired, damaged, unsealed, etc.); nurse explains
          - "approved"   → material is acceptable; verification passes

        Returns:
            {
                "status": "incomplete" | "rejected" | "approved",
                "message": "<nurse's natural spoken response>"
            }
        """

        from datetime import date
        today_str = date.today().strftime("%B %d, %Y")  # e.g. "February 28, 2026"

        clinical_context = clinical_context or {}
        risk_factors = clinical_context.get("risk_factors", [])
        has_diabetes = "diabetes" in risk_factors

        patient_context_note = ""
        if has_diabetes:
            patient_context_note = (
                "\nPATIENT CONTEXT: This patient has Type 2 Diabetes. "
                "Material verification is especially critical as infection risk is elevated. "
                "Be thorough in confirming sterility and condition of materials.\n"
            )

        material_label = (
            "cleaning solution (surgical spirit)"
            if material_type == "solution"
            else "dressing packet (dry sterile dressing)"
            if material_type == "dressing"
            else "material (either the cleaning solution or the dressing packet)"
        )

        system_prompt = (
            "You are a supervising staff nurse verifying materials before a wound cleaning and dressing procedure.\n\n"
            "A nursing student is presenting a material to you for verification.\n\n"

            f"TODAY'S DATE: {today_str}\n"
            "Use this date when judging whether an expiry date the student mentions is past or future.\n\n"
            f"{patient_context_note}"

            "YOUR JOB:\n"
            "Evaluate what the student tells you and return a JSON object with exactly two fields:\n"
            '  "status"  — one of: "incomplete", "rejected", "approved"\n'
            '  "message" — your natural spoken response as the nurse (1–3 sentences)\n\n'

            "VERDICT RULES:\n"
            "1. Use \"incomplete\" if the student has NOT clearly stated:\n"
            "   - Which material they are presenting (surgical spirit / sterile dressing)\n"
            "   - The condition of the bottle or packet (e.g. intact, sealed, damaged)\n"
            "   Ask for whichever detail is missing in a natural, friendly way.\n\n"
            "2. Use \"rejected\" if the student reports or implies ANY problem such as:\n"
            "   - The expiry date mentioned is BEFORE today's date — it is expired\n"
            "     IMPORTANT: if the date is today or any future date, do NOT reject for expiry\n"
            "   - The bottle is cracked, leaking, not sealed, cap is loose\n"
            "   - The dressing packet is torn, wet, moist, open, or no longer sterile\n"
            "   - Any other condition that makes the material unsafe to use\n"
            "   Explain clearly what the problem is and ask the student to get a replacement.\n\n"
            "3. Use \"approved\" ONLY when the student has confirmed:\n"
            "   - The correct material name\n"
            "   - The condition is acceptable (sealed, intact, undamaged, sterile)\n"
            "   - If an expiry date was mentioned, it is today or in the future\n"
            "   Give a brief, clear approval.\n\n"

            f"EXPECTED MATERIAL: {material_label}\n\n"

            "RESPONSE STYLE:\n"
            "- Speak naturally as a real nurse would\n"
            "- Be supportive and professional\n"
            "- Keep the message short (1–3 sentences)\n"
            "- Do NOT ask about expiry dates — only react if the student mentions one\n\n"

            "OUTPUT FORMAT — return ONLY valid JSON, no markdown, no extra text:\n"
            '{"status": "incomplete"|"rejected"|"approved", "message": "..."}\n\n'

            "EXAMPLES:\n"
            'Student: "Can you verify the surgical spirit?"\n'
            '→ {"status": "incomplete", "message": "Sure, what\'s the condition of the bottle — is it sealed and intact?"}\n\n'
            'Student: "Surgical spirit, bottle is intact and sealed."\n'
            '→ {"status": "approved", "message": "Surgical spirit, bottle intact and sealed — looks good. You may use it."}\n\n'
            'Student: "The bottle has a crack in it."\n'
            '→ {"status": "rejected", "message": "A cracked bottle is not safe to use. Please get a new one."}\n\n'
            'Student: "Dressing packet, it\'s torn and wet."\n'
            '→ {"status": "rejected", "message": "The packet is torn and wet — it\'s no longer sterile. Please replace it."}\n\n'
            'Student: "Sterile dressing packet, sealed and undamaged."\n'
            '→ {"status": "approved", "message": "Dry sterile dressing, packet sealed and intact — that\'s fine. You can proceed."}\n\n'
            'Student: "I want to verify this."\n'
            '→ {"status": "incomplete", "message": "Of course — which material are you presenting, and what is its condition?"}\n'
            'Student: "The solution expired last month."\n'
            '→ {"status": "rejected", "message": "This solution is expired and cannot be used. Please get a fresh bottle."}\n'
        )

        user_prompt = (
            f"MATERIAL TYPE DETECTED: {material_type or 'unknown'}\n"
            f"STUDENT MESSAGE: {student_message}\n\n"
            "Respond with the JSON verdict only."
        )

        raw = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2
        )

        # Parse the JSON verdict safely
        try:
            # Strip markdown fences if the model wraps the output
            cleaned = raw.strip().strip("```json").strip("```").strip()
            verdict = json.loads(cleaned)
            status = verdict.get("status", "").lower()
            if status not in ("incomplete", "rejected", "approved"):
                raise ValueError(f"Unexpected status: {status}")
            return {
                "status": status,
                "message": verdict.get("message", raw)
            }
        except Exception as exc:
            # Fallback: treat the raw text as the nurse's message and mark incomplete
            print(f"⚠️  verify_material_conversational JSON parse failed: {exc}\nRaw: {raw}")
            return {
                "status": "incomplete",
                "message": raw or "Could you please describe the material and its condition?"
            }

    async def verify_material(
        self,
        material_type: str,
        material_name: str,
        expiry_date: str,
        package_condition: str
    ) -> str:
        """
        DEPRECATED: Structured verification response (old form-based method).
        Kept for backwards compatibility. Use verify_material_conversational() instead.
        """
        system_prompt = (
            "You are a supervising staff nurse conducting material verification.\n\n"
            "ROLE:\n"
            "- Student is showing you a material for verification\n"
            "- They have stated: name, expiry date, package condition\n"
            "- Provide clear verbal feedback\n\n"
            "VERIFICATION LOGIC:\n"
            "- If package is damaged → Reject and instruct to get new one\n"
            "- If expired → Reject and instruct to get new one\n"
            "- If information incomplete → Ask for missing details\n"
            "- If all correct → Approve clearly\n\n"
            "EXPECTED MATERIALS:\n"
            "- Cleaning solution: Surgical spirit\n"
            "- Dressing: Dry sterile dressing\n\n"
            "RESPONSE STYLE:\n"
            "- Short, professional, clear\n"
            "- State your verification decision explicitly\n"
        )

        user_prompt = (
            f"MATERIAL TYPE: {material_type}\n"
            f"STUDENT DECLARATION:\n"
            f"- Name: {material_name}\n"
            f"- Expiry Date: {expiry_date}\n"
            f"- Package Condition: {package_condition}\n\n"
            "Provide your verification response."
        )

        return await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2
        )
