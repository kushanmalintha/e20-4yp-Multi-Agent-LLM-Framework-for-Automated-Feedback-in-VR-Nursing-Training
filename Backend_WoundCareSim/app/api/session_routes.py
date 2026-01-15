from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict

from app.services.session_manager import SessionManager
from app.services.evaluation_service import EvaluationService
from app.core.coordinator import Coordinator
from app.core.state_machine import Step
from app.utils.schema import EvaluatorResponse
from app.rag.retriever import retrieve_with_rag
from app.agents.patient_agent import PatientAgent

router = APIRouter(prefix="/session", tags=["Session"])

# -------------------------------------------------
# Core services
# -------------------------------------------------

session_manager = SessionManager()
coordinator = Coordinator()
evaluation_service = EvaluationService(
    coordinator=coordinator,
    session_manager=session_manager
)

patient_agent = PatientAgent()
conversation_manager = evaluation_service.conversation_manager

# -------------------------------------------------
# Request models
# -------------------------------------------------

class StartSessionRequest(BaseModel):
    scenario_id: str
    student_id: str


class EvalInput(BaseModel):
    session_id: str
    step: str
    user_input: Optional[str] = None
    evaluator_outputs: List[EvaluatorResponse]
    student_mcq_answers: Optional[Dict[str, str]] = None


class MessageInput(BaseModel):
    session_id: str
    message: str


# -------------------------------------------------
# Routes
# -------------------------------------------------

@router.post("/message")
async def send_message(payload: MessageInput):
    """
    Multi-turn student → patient interaction.
    HISTORY step only.
    No evaluation triggered here.
    """
    session = session_manager.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["current_step"] != Step.HISTORY.value:
        raise HTTPException(
            status_code=400,
            detail="Conversation allowed only during HISTORY step"
        )

    scenario_meta = session["scenario_metadata"]
    patient_history = scenario_meta.get("patient_history", "")

    # Store student message
    conversation_manager.add_turn(
        payload.session_id,
        Step.HISTORY.value,
        "student",
        payload.message
    )

    # Generate patient response
    response = await patient_agent.respond(
        patient_history=patient_history,
        conversation_history=conversation_manager.conversations[payload.session_id][Step.HISTORY.value],
        student_message=payload.message
    )

    # Store patient response
    conversation_manager.add_turn(
        payload.session_id,
        Step.HISTORY.value,
        "patient",
        response
    )

    return {
        "patient_response": response
    }


@router.post("/step")
async def session_step(payload: EvalInput):
    session = session_manager.get_session(payload.session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    current_step = session["current_step"]

    if payload.step != current_step:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid step order. Current step is '{current_step}'."
        )

    # Optional RAG retrieval (text-based steps)
    if payload.user_input:
        try:
            rag_result = await retrieve_with_rag(
                query=payload.user_input,
                scenario_id=session["scenario_id"]
            )
            session_manager.add_rag_result(payload.session_id, rag_result)
        except Exception as e:
            print(f"RAG retrieval failed: {str(e)}")

    # Evaluation aggregation (feedback-only)
    evaluation = await evaluation_service.aggregate_evaluations(
        session_id=payload.session_id,
        evaluator_outputs=payload.evaluator_outputs,
        student_mcq_answers=payload.student_mcq_answers
    )

    # Always allow progression (Week-6 decision)
    next_step = session_manager.advance_step(payload.session_id)

    return {
        "session_id": payload.session_id,
        "current_step": current_step,
        "next_step": next_step,
        "evaluation": evaluation
    }
