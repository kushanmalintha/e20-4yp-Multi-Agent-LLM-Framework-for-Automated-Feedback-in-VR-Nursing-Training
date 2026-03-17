from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Mandatory actions that MUST be performed in the cleaning_and_dressing step
# ---------------------------------------------------------------------------
MANDATORY_ACTIONS: List[str] = [
    "action_initial_hand_hygiene",
    "action_hand_hygiene_after_cleaning",
    "action_verify_solution",
    "action_verify_dressing",
]

ALL_EXPECTED_ACTIONS: List[str] = [
    "action_initial_hand_hygiene",
    "action_clean_trolley",
    "action_hand_hygiene_after_cleaning",
    "action_select_solution",
    "action_verify_solution",
    "action_select_dressing",
    "action_verify_dressing",
    "action_arrange_materials",
    "action_bring_trolley",
]

ACTION_LABELS: Dict[str, str] = {
    "action_initial_hand_hygiene":        "Initial Hand Hygiene",
    "action_clean_trolley":               "Clean the Dressing Trolley",
    "action_hand_hygiene_after_cleaning": "Hand Hygiene After Trolley Cleaning",
    "action_select_solution":             "Select Prescribed Cleaning Solution",
    "action_verify_solution":             "Verify Cleaning Solution with Staff Nurse",
    "action_select_dressing":             "Select Dressing Materials",
    "action_verify_dressing":             "Verify Sterile Dressing Packet with Staff Nurse",
    "action_arrange_materials":           "Arrange Solutions and Materials on Trolley",
    "action_bring_trolley":               "Bring Prepared Trolley to Patient Area",
}

HISTORY_RUBRIC_LABELS: Dict[str, str] = {
    "identity_asked":        "Patient Identity Verified",
    "allergies_asked":       "Allergies Assessed",
    "pain_assessed":         "Pain Assessed",
    "medical_history_asked": "Medical History Obtained",
    "procedure_explained":   "Procedure Explained to Patient",
}


# ---------------------------------------------------------------------------
# Prerequisite map (mirrors ClinicalAgent.PREREQUISITE_MAP)
# ---------------------------------------------------------------------------
PREREQUISITE_MAP: Dict[str, List[str]] = {
    "action_initial_hand_hygiene":        [],
    "action_clean_trolley":               ["action_initial_hand_hygiene"],
    "action_hand_hygiene_after_cleaning": ["action_initial_hand_hygiene", "action_clean_trolley"],
    "action_select_solution":             ["action_initial_hand_hygiene", "action_clean_trolley",
                                           "action_hand_hygiene_after_cleaning"],
    "action_verify_solution":             ["action_initial_hand_hygiene", "action_clean_trolley",
                                           "action_hand_hygiene_after_cleaning", "action_select_solution"],
    "action_select_dressing":             ["action_initial_hand_hygiene", "action_clean_trolley",
                                           "action_hand_hygiene_after_cleaning", "action_select_solution",
                                           "action_verify_solution"],
    "action_verify_dressing":             ["action_initial_hand_hygiene", "action_clean_trolley",
                                           "action_hand_hygiene_after_cleaning", "action_select_solution",
                                           "action_verify_solution", "action_select_dressing"],
    "action_arrange_materials":           ["action_initial_hand_hygiene", "action_clean_trolley",
                                           "action_hand_hygiene_after_cleaning", "action_select_solution",
                                           "action_verify_solution", "action_select_dressing",
                                           "action_verify_dressing"],
    "action_bring_trolley":               ["action_initial_hand_hygiene", "action_clean_trolley",
                                           "action_hand_hygiene_after_cleaning", "action_select_solution",
                                           "action_verify_solution", "action_select_dressing",
                                           "action_verify_dressing", "action_arrange_materials"],
}


class StudentLogService:
    """
    Builds and persists a teacher-readable JSON log for a student session.

    Supports both per-step incremental saving (called after each step completes)
    and full-session log generation (called at any point for a complete snapshot).
    """

    # ------------------------------------------------------------------
    # Public API — Per-step incremental saving
    # ------------------------------------------------------------------

    @staticmethod
    def save_history_step(
        session_id: str,
        session_manager: Any,
        conversation_manager: Any,
    ) -> str:
        """
        Build and persist only the history step data to Firestore.
        Called immediately after the history step evaluation completes.

        Firestore path: students/{student_id}/sessions/{session_id}
        Writes to fields: session (meta), steps.history
        Uses merge=True so subsequent step writes don't overwrite each other.
        """
        from app.utils.firebase_client import db

        session = session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        student_id = session.get("student_id")
        if not student_id:
            raise ValueError("Session is missing student_id.")

        session_meta = StudentLogService._build_session_meta(session_id, session)
        history_data = StudentLogService._build_history_log(
            session_id, session, conversation_manager
        )

        doc_data = {
            "log_generated_at": datetime.now(timezone.utc).isoformat(),
            "session":          session_meta,
            "steps": {
                "history": history_data,
            },
        }

        session_ref = (
            db.collection("students")
              .document(student_id)
              .collection("sessions")
              .document(session_id)
        )
        session_ref.set(doc_data, merge=True)

        # Upsert lightweight student-level summary
        StudentLogService._upsert_student_summary(
            db=db,
            student_id=student_id,
            session_id=session_id,
            session_meta=session_meta,
            partial_update={
                "history_composite_score": (
                    history_data.get("scores", {}).get("composite_score")
                ),
                "history_interpretation": (
                    history_data.get("scores", {}).get("interpretation")
                ),
            },
        )

        firestore_path = f"students/{student_id}/sessions/{session_id}"
        print(f"[LOG] History step saved → {firestore_path}")
        return firestore_path

    @staticmethod
    def save_assessment_step(
        session_id: str,
        session_manager: Any,
    ) -> str:
        """
        Build and persist only the assessment step data to Firestore.
        Called immediately after the assessment step evaluation completes.

        Firestore path: students/{student_id}/sessions/{session_id}
        Writes to fields: session (meta), steps.assessment
        """
        from app.utils.firebase_client import db

        session = session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        student_id = session.get("student_id")
        if not student_id:
            raise ValueError("Session is missing student_id.")

        session_meta    = StudentLogService._build_session_meta(session_id, session)
        assessment_data = StudentLogService._build_assessment_log(session)

        doc_data = {
            "log_generated_at": datetime.now(timezone.utc).isoformat(),
            "session":          session_meta,
            "steps": {
                "assessment": assessment_data,
            },
        }

        session_ref = (
            db.collection("students")
              .document(student_id)
              .collection("sessions")
              .document(session_id)
        )
        session_ref.set(doc_data, merge=True)

        StudentLogService._upsert_student_summary(
            db=db,
            student_id=student_id,
            session_id=session_id,
            session_meta=session_meta,
            partial_update={
                "assessment_score_percentage": assessment_data.get("score_percentage"),
            },
        )

        firestore_path = f"students/{student_id}/sessions/{session_id}"
        print(f"[LOG] Assessment step saved → {firestore_path}")
        return firestore_path

    @staticmethod
    def save_cleaning_step(
        session_id: str,
        session_manager: Any,
    ) -> str:
        """
        Build and persist only the cleaning_and_dressing step data to Firestore.
        Called immediately after the cleaning step completes.

        Firestore path: students/{student_id}/sessions/{session_id}
        Writes to fields: session (meta), steps.cleaning_and_dressing
        """
        from app.utils.firebase_client import db

        session = session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        student_id = session.get("student_id")
        if not student_id:
            raise ValueError("Session is missing student_id.")

        session_meta   = StudentLogService._build_session_meta(session_id, session)
        cleaning_data  = StudentLogService._build_cleaning_log(session)

        doc_data = {
            "log_generated_at": datetime.now(timezone.utc).isoformat(),
            "session":          session_meta,
            "steps": {
                "cleaning_and_dressing": cleaning_data,
            },
        }

        session_ref = (
            db.collection("students")
              .document(student_id)
              .collection("sessions")
              .document(session_id)
        )
        session_ref.set(doc_data, merge=True)

        performed_types = [
            e.get("action_type")
            for e in (session.get("action_events") or [])
        ]
        StudentLogService._upsert_student_summary(
            db=db,
            student_id=student_id,
            session_id=session_id,
            session_meta=session_meta,
            partial_update={
                "hand_hygiene_compliance": (
                    "action_initial_hand_hygiene"        in performed_types
                    and "action_hand_hygiene_after_cleaning" in performed_types
                ),
                "solution_verified":  "action_verify_solution" in performed_types,
                "dressing_verified":  "action_verify_dressing" in performed_types,
                "all_actions_completed": all(
                    a in performed_types for a in ALL_EXPECTED_ACTIONS
                ),
            },
        )

        firestore_path = f"students/{student_id}/sessions/{session_id}"
        print(f"[LOG] Cleaning step saved → {firestore_path}")
        return firestore_path

    # ------------------------------------------------------------------
    # Public API — Full log (snapshot at any point, still usable)
    # ------------------------------------------------------------------

    @staticmethod
    def generate(
        session_id: str,
        session_manager: Any,
        conversation_manager: Any,
    ) -> Dict[str, Any]:
        """
        Build the full log dict from live session data.
        Returns a nested dict representing the complete student log.
        """
        session = session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        log: Dict[str, Any] = {
            "log_generated_at": datetime.now(timezone.utc).isoformat(),
            "session": StudentLogService._build_session_meta(session_id, session),
            "steps": {
                "history":               StudentLogService._build_history_log(
                                             session_id, session, conversation_manager),
                "assessment":            StudentLogService._build_assessment_log(session),
                "cleaning_and_dressing": StudentLogService._build_cleaning_log(session),
            },
            "overall_summary": StudentLogService._build_overall_summary(session),
        }

        return log

    @staticmethod
    def save_to_firestore(log: Dict[str, Any]) -> str:
        """
        Persist the full log to Firestore.
        Uses merge=True so it safely coexists with incremental step writes.
        """
        from app.utils.firebase_client import db

        session_meta: Dict[str, Any] = log.get("session", {})
        student_id: Optional[str]    = session_meta.get("student_id")
        session_id: Optional[str]    = session_meta.get("session_id")

        if not student_id:
            raise ValueError("Log is missing 'session.student_id'.")
        if not session_id:
            raise ValueError("Log is missing 'session.session_id'.")

        session_ref = (
            db.collection("students")
              .document(student_id)
              .collection("sessions")
              .document(session_id)
        )
        # merge=True so incremental step data written earlier is preserved
        session_ref.set(log, merge=True)

        overall: Dict[str, Any]  = log.get("overall_summary", {})
        cleaning: Dict[str, Any] = overall.get("cleaning_preparation", {})

        StudentLogService._upsert_student_summary(
            db=db,
            student_id=student_id,
            session_id=session_id,
            session_meta=session_meta,
            partial_update={
                "history_composite_score":     overall.get("history_composite_score"),
                "history_interpretation":      overall.get("history_interpretation"),
                "assessment_score_percentage": overall.get("assessment_score_percentage"),
                "hand_hygiene_compliance":     cleaning.get("hand_hygiene_compliance"),
                "solution_verified":           cleaning.get("solution_verified"),
                "dressing_verified":           cleaning.get("dressing_verified"),
                "all_actions_completed":       cleaning.get("all_actions_completed"),
                "critical_safety_concerns":    overall.get("critical_safety_concerns", []),
            },
        )

        firestore_path = f"students/{student_id}/sessions/{session_id}"
        return firestore_path

    # ------------------------------------------------------------------
    # Private: Firestore student-level summary upsert
    # ------------------------------------------------------------------

    @staticmethod
    def _upsert_student_summary(
        db: Any,
        student_id: str,
        session_id: str,
        session_meta: Dict[str, Any],
        partial_update: Dict[str, Any],
    ) -> None:
        """
        Upsert the lightweight per-session entry on the parent
        students/{student_id} document so teachers can scan all sessions
        without reading every sub-document.

        partial_update contains only the fields known at the time of the
        call — existing fields on a previously written summary are preserved.
        """
        student_ref  = db.collection("students").document(student_id)
        student_doc  = student_ref.get()

        # Build the base summary for this session (fields always present)
        base: Dict[str, Any] = {
            "session_id":       session_id,
            "scenario_id":      session_meta.get("scenario_id"),
            "scenario_title":   session_meta.get("scenario_title"),
            "started_at":       session_meta.get("started_at"),
            "final_step_reached": session_meta.get("final_step_reached"),
            "log_generated_at": datetime.now(timezone.utc).isoformat(),
        }
        base.update(partial_update)

        if student_doc.exists:
            existing_data: Dict       = student_doc.to_dict() or {}
            sessions_summary: List[Dict] = existing_data.get("sessions_summary", [])

            # Merge with existing entry for this session (preserve earlier fields)
            existing_entry = next(
                (s for s in sessions_summary if s.get("session_id") == session_id),
                {}
            )
            merged_entry = {**existing_entry, **base}

            sessions_summary = [
                s for s in sessions_summary if s.get("session_id") != session_id
            ]
            sessions_summary.append(merged_entry)

            student_ref.update({
                "sessions_summary": sessions_summary,
                "last_session_at":  session_meta.get("started_at"),
                "total_sessions":   len(sessions_summary),
            })
        else:
            student_ref.set({
                "student_id":       student_id,
                "created_at":       datetime.now(timezone.utc).isoformat(),
                "last_session_at":  session_meta.get("started_at"),
                "total_sessions":   1,
                "sessions_summary": [base],
            })

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_session_meta(session_id: str, session: Dict) -> Dict[str, Any]:
        """Top-level session identity and timing."""
        created_at = session.get("created_at", "")
        updated_at = session.get("updated_at", "")

        duration_seconds: Optional[float] = None
        try:
            if created_at and updated_at:
                t_start = datetime.fromisoformat(created_at)
                t_end   = datetime.fromisoformat(updated_at)
                duration_seconds = round((t_end - t_start).total_seconds(), 1)
        except Exception:
            pass

        return {
            "session_id":         session_id,
            "student_id":         session.get("student_id"),
            "scenario_id":        session.get("scenario_id"),
            "scenario_title":     session.get("scenario_metadata", {}).get("title"),
            "started_at":         created_at,
            "last_updated_at":    updated_at,
            "duration_seconds":   duration_seconds,
            "final_step_reached": session.get("current_step"),
            "clinical_context":   session.get("clinical_context", {}),
        }

    # ---- HISTORY ---------------------------------------------------------

    @staticmethod
    def _build_history_log(
        session_id: str,
        session: Dict,
        conversation_manager: Any,
    ) -> Dict[str, Any]:
        """History-taking step log (transcript, communication, scores, narration)."""

        transcript_turns: List[Dict] = (
            conversation_manager.conversations
            .get(session_id, {})
            .get("history", [])
        )

        last_eval: Dict  = session.get("last_evaluation") or {}
        history_eval     = last_eval if last_eval.get("step") == "history" else {}

        scores         = history_eval.get("scores") or {}
        agent_feedback = history_eval.get("agent_feedback") or {}
        narrated       = history_eval.get("narrated_feedback") or {}

        # Communication verdict
        comm_data      = agent_feedback.get("CommunicationAgent", {})
        comm_verdict   = comm_data.get("verdict", "Not evaluated")
        comm_issues    = comm_data.get("issues_detected", [])
        comm_strengths = comm_data.get("strengths", [])

        # Scores
        step_score_raw = scores.get("step_quality_indicator")
        step_score_pct = round(step_score_raw * 100) if step_score_raw is not None else None
        interpretation = scores.get("interpretation")
        agent_scores   = scores.get("agent_scores", {})

        knowledge_score_raw = agent_scores.get("KnowledgeAgent")
        comm_score_raw      = agent_scores.get("CommunicationAgent")

        return {
            "evaluated": bool(history_eval),
            "conversation": {
                "total_turns":        len(transcript_turns),
                "student_turn_count": sum(1 for t in transcript_turns if t.get("speaker") == "student"),
                "patient_turn_count": sum(1 for t in transcript_turns if t.get("speaker") == "patient"),
                "transcript": [
                    {
                        "turn":      i + 1,
                        "speaker":   t.get("speaker"),
                        "text":      t.get("text"),
                        "timestamp": t.get("timestamp"),
                    }
                    for i, t in enumerate(transcript_turns)
                ],
            },
            "communication": {
                "verdict":         comm_verdict,
                "strengths":       comm_strengths,
                "issues_detected": comm_issues,
            },
            "scores": {
                "knowledge_score":     round(knowledge_score_raw * 100) if knowledge_score_raw is not None else None,
                "communication_score": round(comm_score_raw * 100)      if comm_score_raw      is not None else None,
                "composite_score":     step_score_pct,
                "interpretation":      interpretation,
            },
            "narrated_feedback": narrated.get("message_text"),
        }

    @staticmethod
    def _extract_knowledge_flags(history_eval: Dict) -> Dict[str, bool]:
        """Recover KnowledgeAgent boolean flags from stored evaluation payload."""
        candidates = [
            (history_eval.get("agent_feedback") or {})
                .get("KnowledgeAgent", {})
                .get("metadata") or {},
            history_eval.get("metadata") or {},
            history_eval.get("knowledge_flags") or {},
        ]
        flags: Dict[str, bool] = {}
        for source in candidates:
            for key in HISTORY_RUBRIC_LABELS:
                if key in source and key not in flags:
                    flags[key] = bool(source[key])
        return flags

    # ---- ASSESSMENT ------------------------------------------------------

    @staticmethod
    def _build_assessment_log(session: Dict) -> Dict[str, Any]:
        """MCQ assessment step log."""

        last_eval: Dict     = session.get("last_evaluation") or {}
        assessment_eval     = last_eval if last_eval.get("step") == "assessment" else {}
        mcq_result: Dict    = assessment_eval.get("mcq_result") or {}
        mcq_answers: Dict   = session.get("mcq_answers") or {}

        questions: List[Dict] = (
            session.get("scenario_metadata", {}).get("assessment_questions") or []
        )

        question_details: List[Dict] = []
        evaluated_feedback: List[Dict] = mcq_result.get("feedback") or []

        if evaluated_feedback:
            for item in evaluated_feedback:
                question_details.append({
                    "question_id":    item.get("question_id"),
                    "question_text":  item.get("question"),
                    "student_answer": item.get("student_answer"),
                    "correct_answer": item.get("correct_answer"),
                    "is_correct":     item.get("status") == "correct",
                    "explanation":    item.get("explanation"),
                })
        else:
            for q in questions:
                qid         = q.get("id")
                student_ans = mcq_answers.get(qid)
                correct_ans = q.get("correct_answer")
                question_details.append({
                    "question_id":    qid,
                    "question_text":  q.get("question"),
                    "student_answer": student_ans,
                    "correct_answer": correct_ans,
                    "is_correct":     student_ans == correct_ans if student_ans is not None else None,
                    "explanation":    q.get("explanation"),
                })

        total     = mcq_result.get("total_questions") or len(questions)
        correct   = mcq_result.get("correct_count")
        score_pct = round(mcq_result.get("score", 0) * 100) if mcq_result.get("score") is not None else None

        return {
            "evaluated":        bool(assessment_eval),
            "total_questions":  total,
            "correct_count":    correct,
            "score_percentage": score_pct,
            "questions":        question_details,
        }

    # ---- CLEANING & DRESSING ---------------------------------------------

    @staticmethod
    def _build_cleaning_log(session: Dict) -> Dict[str, Any]:
        """Cleaning-and-dressing preparation step log."""

        action_events: List[Dict] = session.get("action_events") or []
        performed_types = [e.get("action_type") for e in action_events]

        # Per-action detail with prerequisite-violation detection
        action_log: List[Dict] = []
        seen: List[str] = []

        for i, event in enumerate(action_events):
            atype        = event.get("action_type", "")
            prereqs      = PREREQUISITE_MAP.get(atype, [])
            missing      = [p for p in prereqs if p not in seen]
            is_duplicate = atype in seen

            action_log.append({
                "sequence":               i + 1,
                "action_type":            atype,
                "action_label":           ACTION_LABELS.get(atype, atype),
                "timestamp":              event.get("timestamp"),
                "is_mandatory":           atype in MANDATORY_ACTIONS,
                "is_duplicate":           is_duplicate,
                "prerequisite_violation": bool(missing),
                "missing_prerequisites": [
                    {"action_type": m, "label": ACTION_LABELS.get(m, m)}
                    for m in missing
                ],
            })

            if not is_duplicate:
                seen.append(atype)

        # Skipped actions
        skipped = [
            {
                "action_type":  a,
                "label":        ACTION_LABELS.get(a, a),
                "is_mandatory": a in MANDATORY_ACTIONS,
            }
            for a in ALL_EXPECTED_ACTIONS
            if a not in performed_types
        ]

        # Verification dialogues
        verification_dialogues: List[Dict] = []
        for event in action_events:
            meta = event.get("metadata") or {}
            if meta.get("auto_detected") and event.get("action_type", "").startswith("action_verify_"):
                verification_dialogues.append({
                    "action_type":   event.get("action_type"),
                    "material_type": meta.get("material_type"),
                    "student_said":  meta.get("student_message"),
                    "nurse_replied": meta.get("nurse_response"),
                    "timestamp":     event.get("timestamp"),
                })

        sequence_violations = sum(
            1 for entry in action_log if entry["prerequisite_violation"]
        )

        return {
            "total_actions_performed": len(action_events),
            "total_actions_expected":  len(ALL_EXPECTED_ACTIONS),
            "completion_percentage":   round(
                len([a for a in ALL_EXPECTED_ACTIONS if a in performed_types])
                / len(ALL_EXPECTED_ACTIONS) * 100
            ),
            "sequence_violations":     sequence_violations,
            "skipped_actions":         skipped,
            "action_timeline":         action_log,
            "verification_dialogues":  verification_dialogues,
        }

    # ---- OVERALL SUMMARY -------------------------------------------------

    @staticmethod
    def _build_overall_summary(session: Dict) -> Dict[str, Any]:
        """Cross-step summary flags for at-a-glance teacher review."""

        last_eval: Dict     = session.get("last_evaluation") or {}
        action_events: List[Dict] = session.get("action_events") or []
        performed_types = [e.get("action_type") for e in action_events]

        history_scores = {}
        if last_eval.get("step") == "history":
            scores = last_eval.get("scores") or {}
            raw    = scores.get("step_quality_indicator")
            history_scores = {
                "composite_score": round(raw * 100) if raw is not None else None,
                "interpretation":  scores.get("interpretation"),
            }

        mcq_score = None
        if last_eval.get("step") == "assessment":
            mcq = last_eval.get("mcq_result") or {}
            raw = mcq.get("score")
            mcq_score = round(raw * 100) if raw is not None else None

        mandatory_skipped = [a for a in MANDATORY_ACTIONS if a not in performed_types]
        hand_hygiene_ok   = (
            "action_initial_hand_hygiene"        in performed_types
            and "action_hand_hygiene_after_cleaning" in performed_types
        )

        return {
            "history_composite_score":      history_scores.get("composite_score"),
            "history_interpretation":       history_scores.get("interpretation"),
            "assessment_score_percentage":  mcq_score,
            "cleaning_preparation": {
                "mandatory_actions_skipped": [
                    {"action_type": a, "label": ACTION_LABELS.get(a, a)}
                    for a in mandatory_skipped
                ],
                "hand_hygiene_compliance":   hand_hygiene_ok,
                "solution_verified":         "action_verify_solution" in performed_types,
                "dressing_verified":         "action_verify_dressing" in performed_types,
                "all_actions_completed":     all(
                    a in performed_types for a in ALL_EXPECTED_ACTIONS
                ),
            },
            "critical_safety_concerns": StudentLogService._list_safety_concerns(
                performed_types, last_eval
            ),
        }

    @staticmethod
    def _list_safety_concerns(
        performed_types: List[str],
        last_eval: Dict,
    ) -> List[str]:
        """Produce a plain-English list of critical safety concerns."""
        concerns: List[str] = []

        if "action_initial_hand_hygiene" not in performed_types:
            concerns.append("Did not perform initial hand hygiene before touching equipment.")

        if "action_hand_hygiene_after_cleaning" not in performed_types:
            concerns.append("Did not perform hand hygiene after cleaning the trolley.")

        if "action_verify_solution" not in performed_types:
            concerns.append("Cleaning solution was NOT verified with the staff nurse.")

        if "action_verify_dressing" not in performed_types:
            concerns.append("Sterile dressing packet was NOT verified with the staff nurse.")

        knowledge_flags = StudentLogService._extract_knowledge_flags(last_eval)
        if last_eval.get("step") == "history" and not knowledge_flags.get("allergies_asked"):
            concerns.append("Patient allergies were NOT assessed during history taking.")

        return concerns
