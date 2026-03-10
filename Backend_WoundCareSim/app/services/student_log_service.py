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
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def generate(
        session_id: str,
        session_manager: Any,
        conversation_manager: Any,
    ) -> Dict[str, Any]:
        """
        Build the full log dict from live session data.

        Args:
            session_id:           The session to log.
            session_manager:      SessionManager instance (holds session state).
            conversation_manager: ConversationManager instance (holds transcripts).

        Returns:
            A nested dict representing the complete student log.
        """
        session = session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        log: Dict[str, Any] = {
            "log_generated_at": datetime.now(timezone.utc).isoformat(),
            "session": StudentLogService._build_session_meta(session_id, session),
            "steps": {
                "history":              StudentLogService._build_history_log(
                                            session_id, session, conversation_manager),
                "assessment":           StudentLogService._build_assessment_log(session),
                "cleaning_and_dressing": StudentLogService._build_cleaning_log(session),
            },
            "overall_summary": StudentLogService._build_overall_summary(session),
        }

        return log

    @staticmethod
    def save_to_firestore(log: Dict[str, Any]) -> str:
        """
        Persist the log to Firestore under:

            students/{student_id}/sessions/{session_id}

        The student document (students/{student_id}) is created or updated
        with a lightweight profile summary so teachers can find students
        quickly without reading every session sub-document.

        Args:
            log: The log dict produced by generate().

        Returns:
            The Firestore path string  "students/{student_id}/sessions/{session_id}".

        Raises:
            ValueError: If student_id or session_id is missing from the log.
            RuntimeError: If the Firestore write fails.
        """
        from app.utils.firebase_client import db  # local import – avoids circular deps

        session_meta: Dict[str, Any] = log.get("session", {})
        student_id: Optional[str]    = session_meta.get("student_id")
        session_id: Optional[str]    = session_meta.get("session_id")

        if not student_id:
            raise ValueError("Log is missing 'session.student_id' – cannot determine Firestore document ID.")
        if not session_id:
            raise ValueError("Log is missing 'session.session_id' – cannot determine Firestore sub-document ID.")

        # ------------------------------------------------------------------
        # 1.  Write the full log as a sub-document:
        #     students/{student_id}/sessions/{session_id}
        # ------------------------------------------------------------------
        session_ref = (
            db.collection("students")
              .document(student_id)
              .collection("sessions")
              .document(session_id)
        )
        session_ref.set(log)

        # ------------------------------------------------------------------
        # 2.  Upsert a lightweight summary on the parent student document
        #     so teachers can see all sessions at a glance.
        # ------------------------------------------------------------------
        overall: Dict[str, Any]  = log.get("overall_summary", {})
        cleaning: Dict[str, Any] = overall.get("cleaning_preparation", {})

        session_summary: Dict[str, Any] = {
            "session_id":                  session_id,
            "scenario_id":                 session_meta.get("scenario_id"),
            "scenario_title":              session_meta.get("scenario_title"),
            "started_at":                  session_meta.get("started_at"),
            "duration_seconds":            session_meta.get("duration_seconds"),
            "final_step_reached":          session_meta.get("final_step_reached"),
            "history_composite_score":     overall.get("history_composite_score"),
            "history_interpretation":      overall.get("history_interpretation"),
            "assessment_score_percentage": overall.get("assessment_score_percentage"),
            "hand_hygiene_compliance":     cleaning.get("hand_hygiene_compliance"),
            "solution_verified":           cleaning.get("solution_verified"),
            "dressing_verified":           cleaning.get("dressing_verified"),
            "all_actions_completed":       cleaning.get("all_actions_completed"),
            "critical_safety_concerns":    overall.get("critical_safety_concerns", []),
            "log_generated_at":            log.get("log_generated_at"),
        }

        student_ref = db.collection("students").document(student_id)
        student_doc = student_ref.get()

        if student_doc.exists:
            # Append this session to the existing sessions_summary array
            existing_data: Dict = student_doc.to_dict() or {}
            sessions_summary: List[Dict] = existing_data.get("sessions_summary", [])

            # Replace summary if session already recorded, otherwise append
            sessions_summary = [
                s for s in sessions_summary if s.get("session_id") != session_id
            ]
            sessions_summary.append(session_summary)

            student_ref.update({
                "sessions_summary": sessions_summary,
                "last_session_at":  session_meta.get("started_at"),
                "total_sessions":   len(sessions_summary),
            })
        else:
            # First session for this student – create the document
            student_ref.set({
                "student_id":      student_id,
                "created_at":      datetime.now(timezone.utc).isoformat(),
                "last_session_at": session_meta.get("started_at"),
                "total_sessions":  1,
                "sessions_summary": [session_summary],
            })

        firestore_path = f"students/{student_id}/sessions/{session_id}"
        return firestore_path

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
                fmt = "%Y-%m-%dT%H:%M:%S.%f"
                t_start = datetime.fromisoformat(created_at)
                t_end   = datetime.fromisoformat(updated_at)
                duration_seconds = round((t_end - t_start).total_seconds(), 1)
        except Exception:
            pass

        return {
            "session_id":        session_id,
            "student_id":        session.get("student_id"),
            "scenario_id":       session.get("scenario_id"),
            "scenario_title":    session.get("scenario_metadata", {}).get("title"),
            "started_at":        created_at,
            "last_updated_at":   updated_at,
            "duration_seconds":  duration_seconds,
            "final_step_reached": session.get("current_step"),
        }

    # ---- HISTORY ---------------------------------------------------------

    @staticmethod
    def _build_history_log(
        session_id: str,
        session: Dict,
        conversation_manager: Any,
    ) -> Dict[str, Any]:
        """History-taking step log."""

        # Pull transcript from ConversationManager
        transcript_turns: List[Dict] = (
            conversation_manager.conversations
            .get(session_id, {})
            .get("history", [])
        )

        # Pull stored evaluation (set by EvaluationService)
        last_eval: Dict = session.get("last_evaluation") or {}
        history_eval = last_eval if last_eval.get("step") == "history" else {}

        scores        = history_eval.get("scores") or {}
        agent_feedback= history_eval.get("agent_feedback") or {}
        narrated      = history_eval.get("narrated_feedback") or {}
        raw_feedback  = history_eval.get("raw_feedback") or []

        # Knowledge flags (boolean checklist)
        knowledge_flags: Dict[str, bool] = {}
        knowledge_data = agent_feedback.get("KnowledgeAgent", {})
        # flags may be stored in metadata inside raw evaluator outputs
        # Try to get from raw_feedback items tagged 'knowledge'
        for item in raw_feedback:
            pass  # raw_feedback items are text-only; flags are in last_evaluation metadata

        # Attempt to recover flags from the stored evaluation payload
        # EvaluationService stores them inside agent_feedback (via coordinator)
        # We look for them recursively
        knowledge_flags = StudentLogService._extract_knowledge_flags(history_eval)

        # Communication verdict
        comm_data    = agent_feedback.get("CommunicationAgent", {})
        comm_verdict = comm_data.get("verdict", "Not evaluated")
        comm_issues  = comm_data.get("issues_detected", [])
        comm_strengths = comm_data.get("strengths", [])

        # Scores
        step_score_raw  = scores.get("step_quality_indicator")
        step_score_pct  = round(step_score_raw * 100) if step_score_raw is not None else None
        interpretation  = scores.get("interpretation")
        agent_scores    = scores.get("agent_scores", {})

        knowledge_score_raw = agent_scores.get("KnowledgeAgent")
        comm_score_raw      = agent_scores.get("CommunicationAgent")

        return {
            "evaluated": bool(history_eval),
            "conversation": {
                "total_turns": len(transcript_turns),
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
            "knowledge_checklist": {
                flag: {
                    "label":     HISTORY_RUBRIC_LABELS.get(flag, flag),
                    "completed": knowledge_flags.get(flag, False),
                }
                for flag in HISTORY_RUBRIC_LABELS
            },
            "communication": {
                "verdict":          comm_verdict,
                "strengths":        comm_strengths,
                "issues_detected":  comm_issues,
            },
            "scores": {
                "knowledge_score":      round(knowledge_score_raw * 100) if knowledge_score_raw is not None else None,
                "communication_score":  round(comm_score_raw * 100)      if comm_score_raw      is not None else None,
                "composite_score":      step_score_pct,
                "interpretation":       interpretation,
            },
            "narrated_feedback": narrated.get("message_text"),
        }

    @staticmethod
    def _extract_knowledge_flags(history_eval: Dict) -> Dict[str, bool]:
        """
        Dig into the stored evaluation payload to find KnowledgeAgent boolean flags.

        EvaluationService stores evaluator outputs via Coordinator which puts
        strengths/issues/explanation/verdict into agent_feedback, but the raw
        metadata flags (identity_asked, etc.) are NOT forwarded by default.

        We therefore scan several candidate locations:
        1. history_eval["agent_feedback"]["KnowledgeAgent"]["metadata"]
        2. history_eval["metadata"]
        3. history_eval["knowledge_flags"]
        """
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

        last_eval: Dict = session.get("last_evaluation") or {}
        assessment_eval = last_eval if last_eval.get("step") == "assessment" else {}
        mcq_result: Dict = assessment_eval.get("mcq_result") or {}

        # Also look at the live mcq_answers stored in session
        # (present before/after complete-step is called)
        mcq_answers: Dict = session.get("mcq_answers") or {}

        questions: List[Dict] = (
            session.get("scenario_metadata", {}).get("assessment_questions") or []
        )

        # Build per-question detail
        question_details: List[Dict] = []

        # Prefer the evaluated feedback list (richer)
        evaluated_feedback: List[Dict] = mcq_result.get("feedback") or []
        if evaluated_feedback:
            for item in evaluated_feedback:
                question_details.append({
                    "question_id":     item.get("question_id"),
                    "question_text":   item.get("question"),
                    "student_answer":  item.get("student_answer"),
                    "correct_answer":  item.get("correct_answer"),
                    "is_correct":      item.get("status") == "correct",
                    "explanation":     item.get("explanation"),
                })
        else:
            # Fallback: build from raw questions + stored answers
            for q in questions:
                qid = q.get("id")
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
            atype      = event.get("action_type", "")
            prereqs    = PREREQUISITE_MAP.get(atype, [])
            missing    = [p for p in prereqs if p not in seen]
            is_duplicate = atype in seen

            action_log.append({
                "sequence":           i + 1,
                "action_type":        atype,
                "action_label":       ACTION_LABELS.get(atype, atype),
                "timestamp":          event.get("timestamp"),
                "is_mandatory":       atype in MANDATORY_ACTIONS,
                "is_duplicate":       is_duplicate,
                "prerequisite_violation": bool(missing),
                "missing_prerequisites": [
                    {"action_type": m, "label": ACTION_LABELS.get(m, m)}
                    for m in missing
                ],
                "metadata":           event.get("metadata") or {},
            })

            if not is_duplicate:
                seen.append(atype)

        # Skipped actions
        skipped = [
            {
                "action_type": a,
                "label":       ACTION_LABELS.get(a, a),
                "is_mandatory": a in MANDATORY_ACTIONS,
            }
            for a in ALL_EXPECTED_ACTIONS
            if a not in performed_types
        ]

        # Safety violations (mandatory actions that were skipped)
        safety_violations = [s for s in skipped if s["is_mandatory"]]

        # Verification dialogues (nurse verify interactions)
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

        # Sequence correctness: count out-of-order actions
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
            "safety_violations": {
                "count":   len(safety_violations),
                "details": safety_violations,
            },
            "skipped_actions":         skipped,
            "action_timeline":         action_log,
            "verification_dialogues":  verification_dialogues,
        }

    # ---- OVERALL SUMMARY -------------------------------------------------

    @staticmethod
    def _build_overall_summary(session: Dict) -> Dict[str, Any]:
        """Cross-step summary flags for at-a-glance teacher review."""

        last_eval: Dict = session.get("last_evaluation") or {}
        action_events: List[Dict] = session.get("action_events") or []
        performed_types = [e.get("action_type") for e in action_events]

        # History score
        history_scores = {}
        if last_eval.get("step") == "history":
            scores = last_eval.get("scores") or {}
            raw = scores.get("step_quality_indicator")
            history_scores = {
                "composite_score":  round(raw * 100) if raw is not None else None,
                "interpretation":   scores.get("interpretation"),
            }

        # MCQ score
        mcq_score = None
        if last_eval.get("step") == "assessment":
            mcq = last_eval.get("mcq_result") or {}
            raw = mcq.get("score")
            mcq_score = round(raw * 100) if raw is not None else None

        # Safety flags
        mandatory_skipped = [a for a in MANDATORY_ACTIONS if a not in performed_types]
        hand_hygiene_ok = (
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

        # History: allergy check is highest-weight item
        knowledge_flags = StudentLogService._extract_knowledge_flags(last_eval)
        if last_eval.get("step") == "history" and not knowledge_flags.get("allergies_asked"):
            concerns.append("Patient allergies were NOT assessed during history taking.")

        return concerns
