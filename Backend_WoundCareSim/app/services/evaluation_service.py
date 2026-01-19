from typing import Dict, List, Any, Optional

from app.rag.retriever import retrieve_with_rag
from app.core.coordinator import Coordinator
from app.services.session_manager import SessionManager
from app.core.state_machine import Step, next_step

from app.utils.mcq_evaluator import MCQEvaluator
from app.utils.schema import EvaluatorResponse
from app.services.conversation_manager import ConversationManager
from app.utils.feedback_schema import Feedback


class EvaluationService:
    """
    FINAL Evaluation Orchestrator

    - Feedback-only (formative)
    - No enforcement or locking
    - Student feedback comes directly from evaluator agents
    - Coordinator is numeric-only (scores, readiness)
    - Staff nurse provides conversational step guidance
    - Enum-safe state machine usage
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
        self.staff_nurse_agent = staff_nurse_agent

    # ------------------------------------------------
    # Context preparation for evaluator agents
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

        if step == Step.HISTORY.value:
            transcript = self.conversation_manager.get_aggregated_transcript(
                session_id=session_id,
                step=step
            )

        elif step in [Step.CLEANING.value, Step.DRESSING.value]:
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
    # Aggregation + feedback construction
    # ------------------------------------------------
    async def aggregate_evaluations(
        self,
        session_id: str,
        evaluator_outputs: List[EvaluatorResponse],
        student_mcq_answers: Optional[Dict[str, str]] = None,
        student_message_to_nurse: Optional[str] = None
    ) -> Dict[str, Any]:

        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        # ---- Convert step string → enum ----
        step_str = evaluator_outputs[0].step.lower()
        current_step = Step(step_str)

        # ---- Coordinator aggregation (NUMERIC ONLY) ----
        coordinator_output = self.coordinator.aggregate(
            evaluations=evaluator_outputs,
            current_step=current_step.value
        )

        # ---- MCQ handling (ASSESSMENT only) ----
        if current_step == Step.ASSESSMENT:
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

        # ------------------------------------------------
        # Build STUDENT-FACING feedback from AGENTS
        # ------------------------------------------------
        feedback_items: List[Dict[str, Any]] = []

        for ev in evaluator_outputs:
            agent_text_parts = []

            if ev.strengths:
                agent_text_parts.append(
                    "Strengths: " + ", ".join(ev.strengths)
                )

            if ev.issues_detected:
                agent_text_parts.append(
                    "Issues: " + ", ".join(ev.issues_detected)
                )

            agent_text_parts.append(
                f"Overall assessment: {ev.verdict}."
            )

            agent_text_parts.append(
                ev.explanation
            )

            feedback_items.append(
                Feedback(
                    text=" ".join(agent_text_parts),
                    speaker="system",
                    category=(
                        "communication"
                        if ev.agent_name == "CommunicationAgent"
                        else "knowledge"
                        if ev.agent_name == "KnowledgeAgent"
                        else "clinical"
                    ),
                    timing="post_step"
                ).to_dict()
            )

        # ---- Staff Nurse conversational guidance ----
        if self.staff_nurse_agent and student_message_to_nurse:
            try:
                next_step_enum = next_step(current_step)
                next_step_str = next_step_enum.value
            except ValueError:
                next_step_str = None

            staff_nurse_text = await self.staff_nurse_agent.respond(
                student_input=student_message_to_nurse,
                current_step=current_step.value,
                next_step=next_step_str
            )

            feedback_items.append(
                Feedback(
                    text=staff_nurse_text,
                    speaker="staff_nurse",
                    category="clinical",
                    timing="post_step"
                ).to_dict()
            )

        # ------------------------------------------------
        # Final payload
        # ------------------------------------------------
        payload = {
            "step": current_step.value,
            "scores": coordinator_output.get("scores"),
            "readiness": coordinator_output.get("readiness"),
            "feedback": feedback_items,

            # ---- INTERNAL EVIDENCE ----
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
