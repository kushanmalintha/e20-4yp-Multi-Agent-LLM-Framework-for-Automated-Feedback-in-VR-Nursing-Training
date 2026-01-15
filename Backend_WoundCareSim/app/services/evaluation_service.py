from typing import Dict, List, Any, Optional
from app.services.scenario_loader import load_scenario
from app.rag.retriever import retrieve_with_rag
from app.core.coordinator import Coordinator
from app.services.session_manager import SessionManager
from app.utils.mcq_evaluator import MCQEvaluator
from app.utils.schema import EvaluatorResponse


class EvaluationService:
    """
    Orchestrates evaluator agents and aggregates feedback.

    WEEK-7 UPDATE:
    - Now accepts aggregated transcript + action events
    - HISTORY step uses conversation transcript
    - CLEANING/DRESSING steps use action events
    - All outputs remain feedback-only

    IMPORTANT:
    - This service does NOT block steps
    - This service does NOT enforce progression
    - All outputs are feedback-only
    """`

    def __init__(
        self,
        coordinator: Coordinator,
        session_manager: SessionManager
    ):
        self.coordinator = coordinator
        self.session_manager = session_manager
        self.mcq_evaluator = MCQEvaluator()

    # ------------------------------------------------
    # Context preparation (UPDATED for Week-7)
    # ------------------------------------------------
    async def prepare_agent_context(
        self,
        scenario_id: str,
        step: str,
        transcript: Optional[str] = None,
        aggregated_transcript: Optional[str] = None,
        action_events: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Prepares context for evaluator agents based on step type.
        
        Week-7 Changes:
        - HISTORY step: uses aggregated_transcript (multi-turn conversation)
        - CLEANING/DRESSING steps: uses action_events
        - Other steps: uses single transcript (backward compatible)
        
        Args:
            scenario_id: Scenario identifier
            step: Current step name
            transcript: Single-turn transcript (legacy/backward compatible)
            aggregated_transcript: Multi-turn conversation history (Week-7)
            action_events: List of action events (Week-7)
        
        Returns:
            Context dictionary for evaluator agents
        """
        scenario_metadata = load_scenario(scenario_id)

        # ------------------------------------------------
        # Step-specific context building
        # ------------------------------------------------
        context = {
            "step": step,
            "scenario_metadata": scenario_metadata,
        }

        # HISTORY step: use aggregated conversation transcript
        if step == "HISTORY":
            final_transcript = aggregated_transcript or transcript or ""
            
            rag = await retrieve_with_rag(
                query=final_transcript,
                scenario_id=scenario_id
            )
            
            context["transcript"] = final_transcript
            context["conversation_transcript"] = final_transcript  # Explicit for clarity
            context["rag_context"] = rag["text"]

        # CLEANING/DRESSING steps: use action events
        elif step in ["CLEANING", "DRESSING"]:
            context["action_events"] = action_events or []
            context["action_summary"] = self._format_action_summary(action_events or [])
            
            # Still provide RAG context based on actions
            action_query = self._create_action_query(action_events or [], step)
            rag = await retrieve_with_rag(
                query=action_query,
                scenario_id=scenario_id
            )
            context["rag_context"] = rag["text"]

        # Other steps: backward compatible (single transcript)
        else:
            final_transcript = transcript or ""
            
            rag = await retrieve_with_rag(
                query=final_transcript,
                scenario_id=scenario_id
            )
            
            context["transcript"] = final_transcript
            context["rag_context"] = rag["text"]

        return context

    # ------------------------------------------------
    # Action event helpers (NEW for Week-7)
    # ------------------------------------------------
    def _format_action_summary(self, action_events: List[Dict[str, Any]]) -> str:
        """
        Formats action events into a readable summary for evaluators.
        
        Args:
            action_events: List of action event dictionaries
        
        Returns:
            Formatted string summary of actions
        """
        if not action_events:
            return "No actions performed yet."
        
        summary_lines = []
        for idx, event in enumerate(action_events, 1):
            action_type = event.get("action_type", "UNKNOWN")
            timestamp = event.get("timestamp", "N/A")
            metadata = event.get("metadata", {})
            
            line = f"{idx}. {action_type} at {timestamp}"
            if metadata:
                line += f" | Details: {metadata}"
            summary_lines.append(line)
        
        return "\n".join(summary_lines)

    def _create_action_query(self, action_events: List[Dict[str, Any]], step: str) -> str:
        """
        Creates a query string from action events for RAG retrieval.
        
        Args:
            action_events: List of action event dictionaries
            step: Current step name
        
        Returns:
            Query string for RAG
        """
        if not action_events:
            return f"{step} procedure actions"
        
        action_types = [event.get("action_type", "") for event in action_events]
        return f"{step} procedure: {', '.join(action_types)}"

    # ------------------------------------------------
    # Evaluation aggregation (UPDATED for Week-7)
    # ------------------------------------------------
    async def aggregate_evaluations(
        self,
        session_id: str,
        evaluator_outputs: List[EvaluatorResponse],
        student_mcq_answers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Aggregates evaluator feedback into a unified response.
        
        Week-7: Now handles both conversation-based and action-based evaluations.
        
        Args:
            session_id: Session identifier
            evaluator_outputs: List of evaluator responses
            student_mcq_answers: MCQ answers (ASSESSMENT step only)
        
        Returns:
            Aggregated feedback dictionary (feedback-only, non-blocking)
        """
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
        # Add context metadata (NEW for Week-7)
        # ------------------------------------------------
        coordinator_output["evaluation_metadata"] = {
            "step": step,
            "evaluation_type": self._determine_evaluation_type(step),
            "timestamp": self._get_current_timestamp()
        }

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
        # Store evaluation snapshot (no decision logic)
        # ------------------------------------------------
        self.session_manager.store_last_evaluation(
            session_id,
            coordinator_output
        )

        # ------------------------------------------------
        # Return feedback-only output
        # ------------------------------------------------
        return coordinator_output

    # ------------------------------------------------
    # Helper methods (NEW for Week-7)
    # ------------------------------------------------
    def _determine_evaluation_type(self, step: str) -> str:
        """
        Determines the type of evaluation based on step.
        
        Args:
            step: Step name
        
        Returns:
            Evaluation type string
        """
        if step == "HISTORY":
            return "CONVERSATION_BASED"
        elif step in ["CLEANING", "DRESSING"]:
            return "ACTION_BASED"
        else:
            return "TEXT_BASED"

    def _get_current_timestamp(self) -> str:
        """
        Returns current timestamp in ISO format.
        
        Returns:
            ISO format timestamp string
        """
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"

    # ------------------------------------------------
    # Input-type helper (Week-7 implementation)
    # ------------------------------------------------
    def determine_input_type(self, payload: Dict[str, Any]) -> str:
        """
        Determines whether the incoming payload is
        text-based or action-based.

        Week-7: Now fully implemented for action handling.
        
        Args:
            payload: Request payload
        
        Returns:
            Input type string ("ACTION" or "TEXT")
        """
        if "action_type" in payload:
            return "ACTION"
        return "TEXT"

    # ------------------------------------------------
    # High-level evaluation orchestration (NEW for Week-7)
    # ------------------------------------------------
    async def evaluate_step(
        self,
        session_id: str,
        step: str,
        transcript: Optional[str] = None,
        aggregated_transcript: Optional[str] = None,
        action_events: Optional[List[Dict[str, Any]]] = None,
        student_mcq_answers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        High-level method to evaluate a step with appropriate context.
        
        This is the main entry point for Week-7 evaluation pipeline.
        
        Args:
            session_id: Session identifier
            step: Step name
            transcript: Single transcript (legacy)
            aggregated_transcript: Multi-turn conversation (HISTORY)
            action_events: Action events (CLEANING/DRESSING)
            student_mcq_answers: MCQ answers (ASSESSMENT)
        
        Returns:
            Aggregated evaluation feedback
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        scenario_id = session["scenario_id"]

        # ------------------------------------------------
        # Prepare context based on step type
        # ------------------------------------------------
        context = await self.prepare_agent_context(
            scenario_id=scenario_id,
            step=step,
            transcript=transcript,
            aggregated_transcript=aggregated_transcript,
            action_events=action_events
        )

        # ------------------------------------------------
        # Invoke evaluator agents through coordinator
        # NOTE: You'll need to update coordinator to accept this context
        # For now, this is a placeholder showing the intended flow
        # ------------------------------------------------
        evaluator_outputs = await self.coordinator.evaluate_with_context(
            step=step,
            context=context
        )

        # ------------------------------------------------
        # Aggregate and return feedback
        # ------------------------------------------------
        return await self.aggregate_evaluations(
            session_id=session_id,
            evaluator_outputs=evaluator_outputs,
            student_mcq_answers=student_mcq_answers
        )