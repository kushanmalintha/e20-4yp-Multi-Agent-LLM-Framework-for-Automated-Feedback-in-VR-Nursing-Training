from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List


from app.services.session_manager import SessionManager
from app.services.evaluation_service import EvaluationService
from app.core.coordinator import Coordinator
from app.core.state_machine import Step
from app.services.action_event_service import ActionEventService
from app.rag.retriever import retrieve_with_rag, extract_prerequisite_map

from app.agents.patient_agent import PatientAgent
from app.agents.communication_agent import CommunicationAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.clinical_agent import ClinicalAgent
from app.agents.staff_nurse_agent import StaffNurseAgent
from app.agents.feedback_narrator_agent import FeedbackNarratorAgent

from app.utils.mcq_evaluator import MCQEvaluator
from app.services.groq_audio_service import GroqAudioService, synthesize_speech
from app.services.student_log_service import StudentLogService
from app.scripts.upload_scenario import save_student_log_to_firestore

# NOTE: The imports above are kept because websocket_routes.py imports
# singletons (session_manager, evaluation_service, clinical_agent, etc.)
# directly from this module. Do not remove them.

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
mcq_evaluator = MCQEvaluator()
audio_service = GroqAudioService()

# -------------------------------------------------
# Request models
# -------------------------------------------------

class StartSessionRequest(BaseModel):
    scenario_id: str
    student_id: str


class MessageInput(BaseModel):
    session_id: str
    message: str


class StaffNurseInput(BaseModel):
    session_id: str
    message: str


class MCQAnswerInput(BaseModel):
    session_id: str
    question_id: str
    answer: str


class ActionInput(BaseModel):
    session_id: str
    action_type: str
    metadata: Optional[Dict[str, Any]] = None


class CompleteStepInput(BaseModel):
    session_id: str
    step: Optional[str] = None
    user_input: Optional[str] = None
    student_mcq_answers: Optional[Dict[str, Any]] = None


# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def is_action_already_performed(session: dict, action_type: str) -> bool:
    """
    Check if an action has already been performed in this session.
    """
    action_events = session.get("action_events", [])
    return any(event["action_type"] == action_type for event in action_events)


async def _safe_tts(text: str, role: str) -> Optional[Dict[str, Any]]:
    """
    Convert text to speech without breaking request flow.
    """
    if not text:
        return None
    try:
        return await synthesize_speech(text=text, role=role, audio_service=audio_service)
    except Exception as exc:
        print(f"⚠️  TTS failed: {exc}")
        return None


# -------------------------------------------------
# Routes
# -------------------------------------------------

@router.post("/start")
def start_session(payload: StartSessionRequest):
    """
    Start a new training session.
    """
    session_id = session_manager.create_session(
        scenario_id=payload.scenario_id,
        student_id=payload.student_id
    )
    print(f"\n[STEP START] current_step=history\n")
    return {"session_id": session_id, "session_token": session_manager.get_session(session_id).get("session_token")}


@router.get("/{session_id}")
def get_session_info(session_id: str):
    """
    Get current session state and information.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "scenario_id": session["scenario_id"],
        "student_id": session["student_id"],
        "current_step": session["current_step"],
        "scenario_metadata": session["scenario_metadata"],
        "last_evaluation": session.get("last_evaluation"),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
        "session_token": session.get("session_token")
    }


def _detect_verification_request(message: str) -> tuple[bool, str]:
    """
    Detect if student message is a verification request and which material type.

    Only determines intent and material type — all actual validation is done by the LLM nurse.

    Returns:
        (is_verification, material_type)
        - is_verification: True if verification intent detected
        - material_type: "solution", "dressing", or "" (unknown, LLM will ask)
    """
    message_lower = message.lower()

    verification_keywords = [
        "verify", "check", "confirm", "is this correct", "is this right",
        "can you check", "could you check", "look at this", "inspect"
    ]

    solution_keywords = [
        "solution", "surgical spirit", "spirit", "bottle", "liquid", "cleaning solution"
    ]

    dressing_keywords = [
        "dressing", "packet", "pack", "bandage", "sterile dressing", "gauze"
    ]

    has_verification_keyword = any(keyword in message_lower for keyword in verification_keywords)
    mentions_condition = any(word in message_lower for word in ["intact", "sealed", "damaged", "condition", "package"])

    # Verification intent: explicit keyword OR student is already describing material condition
    is_verification = has_verification_keyword or mentions_condition

    if not is_verification:
        return False, ""

    has_solution = any(keyword in message_lower for keyword in solution_keywords)
    has_dressing = any(keyword in message_lower for keyword in dressing_keywords)

    if has_solution:
        material_type = "solution"
    elif has_dressing:
        material_type = "dressing"
    else:
        material_type = ""  # LLM nurse will ask which material

    return True, material_type


async def _handle_verification_as_action(
    session: dict,
    student_message: str,
    material_type: str
) -> dict:
    """
    Handle a verification request entirely through the LLM nurse.

    The LLM nurse evaluates the student's message and returns a structured verdict:
      - "incomplete"  → student hasn't provided enough details; nurse asks naturally
      - "rejected"    → something is wrong with the material; nurse explains why
      - "approved"    → material is acceptable; action is recorded

    No hard-coded keyword checks are used. The LLM is the sole judge.
    """
    session_id = list(session_manager.sessions.keys())[
        list(session_manager.sessions.values()).index(session)
    ]

    action_type = f"action_verify_{material_type}" if material_type else "action_verify_unknown"

    # Guard: already verified this material
    if material_type and is_action_already_performed(session, action_type):
        performed_count = len(session.get("action_events", []))
        msg = f"You've already verified the {material_type} with me. You can proceed to the next step."
        staff_nurse_audio = await _safe_tts(msg, role="staff_nurse")
        return {
            "staff_nurse_response": msg,
            "current_step": session["current_step"],
            "is_verification": True,
            "action_recorded": False,
            "already_performed": True,
            "staff_nurse_audio": staff_nurse_audio,
            "feedback_audio": None,
            "feedback": {
                "message": msg,
                "status": "duplicate",
                "can_proceed": True,
                "total_actions_so_far": performed_count,
            },
        }

    # Get cached RAG guidelines
    rag_guidelines = session.get("cached_rag_guidelines", "")
    if not rag_guidelines:
        rag_result = await retrieve_with_rag(
            query="wound cleaning and dressing preparation steps sequence prerequisites verification",
            scenario_id=session["scenario_id"]
        )
        rag_guidelines = rag_result.get("text", "")

    performed_actions = session.get("action_events", [])

    # LLM nurse evaluates the message and returns structured verdict
    staff_nurse = StaffNurseAgent()
    verdict = await staff_nurse.verify_material_conversational(
        student_message=student_message,
        material_type=material_type
    )

    # verdict = {"status": "incomplete" | "rejected" | "approved", "message": "..."}
    nurse_response = verdict.get("message", "")
    verdict_status = verdict.get("status", "incomplete")

    print("\n" + "=" * 60)
    print(f"VERIFICATION — Material: {material_type or 'unknown'} | Verdict: {verdict_status}")
    print("=" * 60)
    print(f"Student : {student_message}")
    print(f"Nurse   : {nurse_response}")
    print("=" * 60 + "\n")

    staff_nurse_audio = await _safe_tts(nurse_response, role="staff_nurse")

    # Only record the action when the nurse approves
    if verdict_status == "approved" and material_type:
        real_time_feedback = await clinical_agent.get_real_time_feedback(
            action_type=action_type,
            performed_actions=performed_actions,
            rag_guidelines=rag_guidelines
        )
        result = action_event_service.record_action(
            session_id=session_id,
            action_type=action_type,
            step=session["current_step"],
            metadata={
                "material_type": material_type,
                "student_message": student_message,
                "nurse_response": nurse_response,
                "auto_detected": True
            }
        )
        return {
            "staff_nurse_response": nurse_response,
            "current_step": session["current_step"],
            "is_verification": True,
            "action_recorded": True,
            "action_type": action_type,
            "timestamp": result.get("timestamp"),
            "already_performed": False,
            "staff_nurse_audio": staff_nurse_audio,
            "feedback_audio": None,
            "feedback": {
                "message": "Verification recorded.",
                "status": real_time_feedback.get("status"),
                "can_proceed": real_time_feedback.get("can_proceed"),
                "total_actions_so_far": real_time_feedback.get("total_actions_so_far"),
            }
        }

    # incomplete or rejected — do not record the action
    feedback_status = "missing_details" if verdict_status == "incomplete" else "invalid_material"
    return {
        "staff_nurse_response": nurse_response,
        "current_step": session["current_step"],
        "is_verification": True,
        "action_recorded": False,
        "already_performed": False,
        "staff_nurse_audio": staff_nurse_audio,
        "feedback_audio": None,
        "feedback": {
            "message": nurse_response,
            "status": feedback_status,
            "can_proceed": False,
            "total_actions_so_far": len(performed_actions),
        },
    }


@router.post("/complete-step")
async def complete_step(payload: CompleteStepInput):
    """
    Complete the current step via REST and advance session state.
    """
    session = session_manager.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    current_step = session.get("current_step")
    if payload.step and payload.step != current_step:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid step completion request. Current step is '{current_step}'.",
        )

    response: Dict[str, Any] = {
        "session_id": payload.session_id,
        "current_step": current_step,
    }

    if current_step == Step.HISTORY.value:
        context = await evaluation_service.prepare_agent_context(
            session_id=payload.session_id,
            step=current_step,
        )

        evaluator_outputs = [
            await communication_agent.evaluate(
                current_step=current_step,
                student_input=context["transcript"],
                scenario_metadata=context["scenario_metadata"],
                rag_response=context["rag_context"],
            ),
            await knowledge_agent.evaluate(
                current_step=current_step,
                student_input=context["transcript"],
                scenario_metadata=context["scenario_metadata"],
                rag_response=context["rag_context"],
            ),
        ]

        evaluation = await evaluation_service.aggregate_evaluations(
            session_id=payload.session_id,
            evaluator_outputs=evaluator_outputs,
            student_mcq_answers=None,
            student_message_to_nurse=payload.user_input,
        )

        conversation_manager.clear_step(payload.session_id, Step.HISTORY.value)

        feedback_payload = {
            "narrated_feedback": evaluation.get("narrated_feedback"),
            "score": evaluation.get("scores", {}).get("step_quality_indicator"),
            "interpretation": evaluation.get("scores", {}).get("interpretation"),
        }
        narrated_text = (evaluation.get("narrated_feedback") or {}).get("message_text", "")
        response["feedback_type"] = "history"
        response["feedback"] = feedback_payload
        response["feedback_audio"] = await _safe_tts(narrated_text, role="feedback")
        session["pending_step_transition_confirmation"] = False

    elif current_step == Step.ASSESSMENT.value:
        mcq_answers = session.get("mcq_answers", payload.student_mcq_answers or {})
        evaluation = await evaluation_service.aggregate_evaluations(
            session_id=payload.session_id,
            evaluator_outputs=[],
            student_mcq_answers=mcq_answers,
            student_message_to_nurse=payload.user_input,
        )

        mcq_result = evaluation.get("mcq_result")
        summary_text = None
        if mcq_result:
            summary_text = (
                f"You answered {mcq_result.get('correct_count')} out of "
                f"{mcq_result.get('total_questions')} questions correctly."
            )

        response["feedback_type"] = "assessment"
        response["feedback"] = {
            "mcq_result": mcq_result,
            "summary_text": summary_text,
        }
        response["feedback_audio"] = await _safe_tts(summary_text or "", role="assessment_feedback")
        session["mcq_answers"] = {}

    elif current_step == Step.CLEANING_AND_DRESSING.value:
        session["action_events"] = []
        session.pop("cached_rag_guidelines", None)
        session.pop("cached_prerequisite_map", None)
        response["feedback_type"] = "cleaning_and_dressing"
        response["feedback"] = None

    else:
        raise HTTPException(status_code=400, detail=f"Step '{current_step}' cannot be completed.")

    next_step = session_manager.advance_step(payload.session_id)
    response["next_step"] = next_step
    print(f"\n[STEP START] current_step={next_step}\n")

    if next_step == Step.CLEANING_AND_DRESSING.value:
        rag_result = await retrieve_with_rag(
            query="wound cleaning and dressing preparation steps sequence prerequisites required actions",
            scenario_id=session["scenario_id"],
        )
        rag_text = rag_result.get("text", "")
        session["cached_rag_guidelines"] = rag_text
        session["cached_prerequisite_map"] = await extract_prerequisite_map(
            rag_text=rag_text,
            base_agent=clinical_agent,
        )

    response["session_end"] = next_step == Step.COMPLETED.value

    # Auto-save log to Firestore when session reaches COMPLETED
    if next_step == Step.COMPLETED.value:
        try:
            log = StudentLogService.generate(
                session_id=payload.session_id,
                session_manager=session_manager,
                conversation_manager=conversation_manager,
            )
            firestore_path = save_student_log_to_firestore(log)
            response["log_firestore_path"] = firestore_path
        except Exception as exc:
            print(f"[LOG] ⚠️  Failed to save student log: {exc}")

    return response


@router.get("/{session_id}/log")
async def get_session_log(session_id: str):
    """
    Generate and return the full structured student log for a session.
    The log is also saved to disk at  logs/<session_id>.json.
    Can be called at any point during or after the session.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        log = StudentLogService.generate(
            session_id=session_id,
            session_manager=session_manager,
            conversation_manager=conversation_manager,
        )
        firestore_path = save_student_log_to_firestore(log)
        print(f"[LOG] Student log saved to Firestore → {firestore_path}")
        return log
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Log generation failed: {exc}"
        ) from exc
