from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.services.session_manager import SessionManager
from app.services.evaluation_service import EvaluationService
from app.core.coordinator import Coordinator
from app.core.state_machine import Step
from app.services.action_event_service import ActionEventService

from app.agents.patient_agent import PatientAgent
from app.agents.communication_agent import CommunicationAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.clinical_agent import ClinicalAgent
from app.agents.staff_nurse_agent import StaffNurseAgent
from app.agents.feedback_narrator_agent import FeedbackNarratorAgent

router = APIRouter(prefix="/session", tags=["Session"])

# -------------------------------------------------
# Core services (singletons)
# -------------------------------------------------

session_manager = SessionManager()
coordinator = Coordinator()

evaluation_service = EvaluationService(
    coordinator=coordinator,
    session_manager=session_manager,
    staff_nurse_agent=StaffNurseAgent(),
    feedback_narrator_agent=FeedbackNarratorAgent(),
)

action_event_service = ActionEventService(session_manager)

patient_agent = PatientAgent()
conversation_manager = evaluation_service.conversation_manager

communication_agent = CommunicationAgent()
knowledge_agent = KnowledgeAgent()
clinical_agent = ClinicalAgent()

# -------------------------------------------------
# Request models
# -------------------------------------------------

class StartSessionRequest(BaseModel):
    scenario_id: str
    student_id: str


class MessageInput(BaseModel):
    session_id: str
    message: str


class StepInput(BaseModel):
    session_id: str
    step: str
    user_input: Optional[str] = None
    student_mcq_answers: Optional[Dict[str, str]] = None
    action: Optional[Dict[str, Any]] = None  # {action_type, metadata}


# -------------------------------------------------
# Routes
# -------------------------------------------------

@router.post("/start")
def start_session(payload: StartSessionRequest):
    session_id = session_manager.create_session(
        scenario_id=payload.scenario_id,
        student_id=payload.student_id
    )
    return {"session_id": session_id}


@router.post("/message")
async def send_message(payload: MessageInput):
    """
    Multi-turn student ↔ patient conversation.
    HISTORY step only.
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
    patient_history = scenario_meta["patient_history"]

    conversation_manager.add_turn(
        payload.session_id,
        Step.HISTORY.value,
        "student",
        payload.message
    )

    response = await patient_agent.respond(
        patient_history=patient_history,
        conversation_history=conversation_manager.conversations[payload.session_id][Step.HISTORY.value],
        student_message=payload.message
    )

    conversation_manager.add_turn(
        payload.session_id,
        Step.HISTORY.value,
        "patient",
        response
    )

    return {"patient_response": response}


@router.post("/step")
async def run_step(payload: StepInput):
    """
    Unified step handler (Week-9 FINAL).
    """
    session = session_manager.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    current_step = session["current_step"]

    if payload.step != current_step:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid step. Current step is '{current_step}'."
        )

    # ---------------------------------------------
    # Record action event (CLEANING / DRESSING)
    # ---------------------------------------------
    if payload.action:
        action_event_service.record_action(
            session_id=payload.session_id,
            action_type=payload.action["action_type"],
            step=current_step,
            metadata=payload.action.get("metadata")
        )

    # ---------------------------------------------
    # Prepare evaluation context
    # ---------------------------------------------
    context = await evaluation_service.prepare_agent_context(
        session_id=payload.session_id,
        step=current_step
    )

    evaluator_outputs = []

    if current_step == Step.HISTORY.value:
        evaluator_outputs.append(
            await communication_agent.evaluate(
                current_step=current_step,
                student_input=context["transcript"],
                scenario_metadata=context["scenario_metadata"],
                rag_response=context["rag_context"]
            )
        )
        evaluator_outputs.append(
            await knowledge_agent.evaluate(
                current_step=current_step,
                student_input=context["transcript"],
                scenario_metadata=context["scenario_metadata"],
                rag_response=context["rag_context"]
            )
        )

    elif current_step == Step.ASSESSMENT.value:
        evaluator_outputs.append(
            await knowledge_agent.evaluate(
                current_step=current_step,
                student_input="MCQ Assessment",
                scenario_metadata=context["scenario_metadata"],
                rag_response=context["rag_context"]
            )
        )

    else:  # CLEANING / DRESSING
        evaluator_outputs.append(
            await clinical_agent.evaluate(
                current_step=current_step,
                student_input=str(context["action_events"]),
                scenario_metadata=context["scenario_metadata"],
                rag_response=context["rag_context"]
            )
        )

    # ---------------------------------------------
    # Aggregate + narrate feedback
    # ---------------------------------------------
    evaluation = await evaluation_service.aggregate_evaluations(
        session_id=payload.session_id,
        evaluator_outputs=evaluator_outputs,
        student_mcq_answers=payload.student_mcq_answers,
        student_message_to_nurse=payload.user_input
    )

    # ---------------------------------------------
    # Advance step (always allowed)
    # ---------------------------------------------
    next_step = session_manager.advance_step(payload.session_id)

    return {
        "session_id": payload.session_id,
        "current_step": current_step,
        "next_step": next_step,
        "evaluation": evaluation
    }
