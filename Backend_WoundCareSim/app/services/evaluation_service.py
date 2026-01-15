from typing import Dict, List, Any, Optional

from app.services.scenario_loader import load_scenario
from app.rag.retriever import retrieve_with_rag
from app.core.coordinator import Coordinator
from app.services.session_manager import SessionManager
from app.utils.mcq_evaluator import MCQEvaluator
from app.utils.schema import EvaluatorResponse
from app.services.conversation_manager import ConversationManager


class EvaluationService:
    """
    Orchestrates evaluator agents and aggregates feedback.

    IMPORTANT (Week-6 / Week-7):
    - Feedback-only
    - No blocking
    - No progression enforcement
    """

    def __init__(
        self,
        coordinator: Coordinator,
        session_manager: SessionManager
    ):
        self.coordinator = coordinator
        self.session_manager = session_manager
        self.mcq_evaluator = MCQEvaluator()

        # Week-7: multi-turn conversation support
        self.conversation_manager = ConversationManager()

    # ------------------------------------------------
    # Context preparation (Week-7 aware)
    # ------------------------------------------------
    async def prepare_agent_context(
        self,
        session_id: str,
        scenario_id: str,
        step: str
    ) -> Dict[str, Any]:

        scenario_metadata = load_scenario(scenario_id)

        # HISTORY uses aggregated multi-turn transcript
        if step == "HISTORY":
            transcript = self.conversation_manager.get_aggregated_transcript(
                session_id=session_id,
                step=step
            )
        else:
            transcript = ""

        rag = await retrieve_with_rag(
            query=transcript or "clinical nursing evaluation",
            scenario_id=scenario_id
        )

        return {
            "transcript": transcript,
            "step": step,
            "scenario_metadata": scenario_metadata,
            "rag_context": rag.get("text", "")
        }

    # ------------------------------------------------
    # Evaluation aggregation (feedback-only)
    # ------------------------------------------------
    async def aggregate_evaluations(
        self,
        session_id: str,
        evaluator_outputs: List[EvaluatorResponse],
        student_mcq_answers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:

        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        step = evaluator_outputs[0].step

        # ------------------------------------------------
        # Aggregate evaluator feedback
        # ------------------------------------------------
        coordinator_output = self.coordinator.aggregate(
            evaluations=evaluator_outputs,
            current_step=step
        )

        # ------------------------------------------------
        # MCQ enrichment (ASSESSMENT only, formative)
        # ------------------------------------------------
        if step == "ASSESSMENT":
            scenario_meta = load_scenario(session["scenario_id"])
            assessment_questions = scenario_meta.get("assessment_questions")

            if isinstance(assessment_questions, list) and student_mcq_answers:
                mcq_result = self.mcq_evaluator.validate_mcq_answers(
                    student_answers=student_mcq_answers,
                    assessment_questions=assessment_questions
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
        # Store evaluation snapshot (feedback only)
        # ------------------------------------------------
        self.session_manager.store_last_evaluation(
            session_id=session_id,
            evaluation=coordinator_output
        )

        return coordinator_output

    # ------------------------------------------------
    # Input-type helper (Week-7 prep)
    # ------------------------------------------------
    def determine_input_type(self, payload: Dict[str, Any]) -> str:
        """
        Determines whether the incoming payload is
        text-based or action-based.

        NOTE:
        Action handling is introduced later (Week-7+).
        """
        if "action_type" in payload:
            return "ACTION"
        return "TEXT"
