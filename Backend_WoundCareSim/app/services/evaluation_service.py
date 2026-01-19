from typing import Dict, List, Any, Optional

from app.rag.retriever import retrieve_with_rag
from app.core.coordinator import Coordinator
from app.services.session_manager import SessionManager
from app.utils.mcq_evaluator import MCQEvaluator
from app.utils.schema import EvaluatorResponse
from app.services.conversation_manager import ConversationManager
from app.services.history_completeness_service import HistoryCompletenessService
from app.utils.feedback_schema import Feedback


class EvaluationService:
    """
    Week-8 FINAL Evaluation Orchestrator

    - Feedback-only
    - No enforcement
    - Staff nurse is advisory only
    - Agent outputs logged as debug evidence
    """

    def __init__(
        self,
        coordinator: Coordinator,
        session_manager: SessionManager,
        staff_nurse_agent: Optional[Any] = None
    ):
        self.coordinator = coordinator
        self.session_manager = session_manager
        self.mcq_evaluator = MCQEvaluator()
        self.conversation_manager = ConversationManager()
        self.history_service = HistoryCompletenessService()
        self.staff_nurse_agent = staff_nurse_agent

    # ------------------------------------------------
    # Context preparation
    # ------------------------------------------------
    async def prepare_agent_context(
        self,
        session_id: str,
        step: str
    ) -> Dict[str, Any]:

        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        scenario_metadata = session["scenario_metadata"]

        transcript = ""
        action_events: List[Dict[str, Any]] = []

        if step == "HISTORY":
            transcript = self.conversation_manager.get_aggregated_transcript(
                session_id=session_id,
                step=step
            )

        elif step in ["CLEANING", "DRESSING"]:
            action_events = session.get("action_events", [])

        rag_query = transcript or (
            f"{step} procedure actions"
            if action_events
            else "clinical nursing evaluation"
        )

        rag = await retrieve_with_rag(
            query=rag_query,
            scenario_id=session["scenario_id"]
        )

        return {
            "step": step,
            "scenario_metadata": scenario_metadata,
            "transcript": transcript,
            "action_events": action_events,
            "rag_context": rag.get("text", "")
        }

    # ------------------------------------------------
    # Evaluation aggregation
    # ------------------------------------------------
    async def aggregate_evaluations(
        self,
        session_id: str,
        evaluator_outputs: List[EvaluatorResponse],
        student_mcq_answers: Optional[Dict[str, str]] = None,
        request_staff_permission: bool = False,
        student_request_text: Optional[str] = None
    ) -> Dict[str, Any]:

        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        step = evaluator_outputs[0].step

        # ---- Coordinator aggregation (scores + readiness) ----
        coordinator_output = self.coordinator.aggregate(
            evaluations=evaluator_outputs,
            current_step=step
        )

        # ---- MCQ handling (ASSESSMENT only) ----
        if step == "ASSESSMENT":
            questions = session["scenario_metadata"].get(
                "assessment_questions", []
            )

            if questions and student_mcq_answers:
                mcq_result = self.mcq_evaluator.validate_mcq_answers(
                    student_answers=student_mcq_answers,
                    assessment_questions=questions
                )
            else:
                mcq_result = {
                    "total_questions": 0,
                    "correct_count": 0,
                    "feedback": [],
                    "summary": "No MCQ questions available"
                }

            coordinator_output["mcq_result"] = mcq_result

        # ---- HISTORY completeness (system feedback only) ----
        history_summary = None
        if step == "HISTORY":
            transcript = self.conversation_manager.get_aggregated_transcript(
                session_id=session_id,
                step=step
            )

            required_points = session["scenario_metadata"].get(
                "required_conversation_points", []
            )

            history_summary = self.history_service.analyze(
                transcript=transcript,
                required_points=required_points
            )

        # ---- Staff Nurse interaction (plain text only) ----
        staff_nurse_text = None
        if (
            step == "HISTORY"
            and request_staff_permission
            and self.staff_nurse_agent
            and student_request_text
        ):
            staff_nurse_text = await self.staff_nurse_agent.respond(
                student_input=student_request_text,
                scenario_metadata=session["scenario_metadata"]
            )

        # ---- Build user-facing feedback ----
        feedback_items: List[Dict[str, Any]] = []

        # Aggregated evaluator feedback (summary only)
        feedback_items.append(
            Feedback(
                text=coordinator_output.get("overall_feedback", ""),
                speaker="system",
                category="knowledge",
                timing="post_step"
            ).to_dict()
        )

        # History completeness feedback
        if history_summary:
            feedback_items.append(
                Feedback(
                    text=history_summary["summary"],
                    speaker="system",
                    category="knowledge",
                    timing="post_step"
                ).to_dict()
            )

        # Staff nurse feedback
        if staff_nurse_text:
            feedback_items.append(
                Feedback(
                    text=staff_nurse_text,
                    speaker="staff_nurse",
                    category="clinical",
                    timing="post_step"
                ).to_dict()
            )

        # ---- Final payload ----
        payload = {
            "step": step,
            "scores": coordinator_output.get("scores"),
            "readiness": coordinator_output.get("readiness"),
            "feedback": feedback_items,

            # 🔍 DEBUG / EVIDENCE BLOCK (Week-8)
            "debug": {
                "agent_outputs": [
                    ev.dict() for ev in evaluator_outputs
                ]
            }
        }

        self.session_manager.store_last_evaluation(
            session_id=session_id,
            evaluation=payload
        )

        return payload
