from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from app.services.session_manager import SessionManager
from app.services.evaluation_service import EvaluationService
from app.core.coordinator import Coordinator
from app.core.state_machine import Step
from app.services.action_event_service import ActionEventService
from app.rag.retriever import retrieve_with_rag

from app.agents.patient_agent import PatientAgent
from app.agents.communication_agent import CommunicationAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.clinical_agent import ClinicalAgent
from app.agents.staff_nurse_agent import StaffNurseAgent
from app.agents.feedback_narrator_agent import FeedbackNarratorAgent

from app.utils.mcq_evaluator import MCQEvaluator
from app.services.groq_audio_service import GroqAudioService, synthesize_speech

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


class StepInput(BaseModel):
    session_id: str
    step: str
    user_input: Optional[str] = None
    student_mcq_answers: Optional[Dict[str, str]] = None


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


# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def is_action_already_performed(session: dict, action_type: str) -> bool:
    """
    Check if an action has already been performed in this session.
    
    Args:
        session: Session dictionary
        action_type: Action type to check
    
    Returns:
        True if action already performed, False otherwise
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
    Detect if student message is a verification request.
    
    Returns:
        (is_verification, material_type)
        - is_verification: True if verification detected
        - material_type: "solution" or "dressing" or ""
    """
    message_lower = message.lower()
    
    # Verification keywords
    verification_keywords = [
        "verify", "check", "confirm", "is this correct", "is this right",
        "can you check", "could you check", "look at this", "inspect"
    ]
    
    # Material keywords
    solution_keywords = [
        "solution", "surgical spirit", "spirit", "bottle", "liquid", "cleaning solution"
    ]
    
    dressing_keywords = [
        "dressing", "packet", "pack", "bandage", "sterile dressing", "gauze"
    ]
    
    # Check if it's a verification request
    has_verification_keyword = any(keyword in message_lower for keyword in verification_keywords)
    
    # Additional indicators
    mentions_expiry = any(word in message_lower for word in ["expire", "expiry", "expiration", "date"])
    mentions_condition = any(word in message_lower for word in ["intact", "sealed", "damaged", "condition", "package"])
    
    # Must have verification keyword OR (expiry + condition mention)
    is_verification = has_verification_keyword or (mentions_expiry and mentions_condition)
    
    if not is_verification:
        return False, ""
    
    # Determine material type
    has_solution = any(keyword in message_lower for keyword in solution_keywords)
    has_dressing = any(keyword in message_lower for keyword in dressing_keywords)
    
    if has_solution:
        material_type = "solution"
    elif has_dressing:
        material_type = "dressing"
    else:
        # Default to solution if unclear
        material_type = "solution"
    
    return True, material_type


async def _handle_verification_as_action(
    session: dict,
    student_message: str,
    material_type: str
) -> dict:
    """
    Handle verification request as an action.
    
    This is called when nurse detects verification in conversation.
    """
    session_id = list(session_manager.sessions.keys())[
        list(session_manager.sessions.values()).index(session)
    ]
    
    action_type = f"action_verify_{material_type}"
    
    # ⭐ FIX #1: Check if action already performed
    if is_action_already_performed(session, action_type):
        staff_nurse_audio = await _safe_tts(
            f"You've already verified the {material_type} with me. You can proceed to the next step.",
            role="staff_nurse",
        )
        return {
            "staff_nurse_response": f"You've already verified the {material_type} with me. You can proceed to the next step.",
            "current_step": session["current_step"],
            "is_verification": True,
            "action_recorded": False,
            "already_performed": True,
            "staff_nurse_audio": staff_nurse_audio,
        }
    
    # Get cached RAG guidelines
    rag_guidelines = session.get("cached_rag_guidelines", "")
    
    if not rag_guidelines:
        rag_result = await retrieve_with_rag(
            query="wound cleaning and dressing preparation steps sequence prerequisites verification",
            scenario_id=session["scenario_id"]
        )
        rag_guidelines = rag_result.get("text", "")
    
    # Generate nurse conversational response
    staff_nurse = StaffNurseAgent()
    nurse_response = await staff_nurse.verify_material_conversational(
        student_message=student_message,
        material_type=material_type
    )
    
    # Get current action events BEFORE recording
    performed_actions = session.get("action_events", [])
    
    # Get real-time feedback
    real_time_feedback = await clinical_agent.get_real_time_feedback(
        action_type=action_type,
        performed_actions=performed_actions,
        rag_guidelines=rag_guidelines
    )
    
    # Record the verification action
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
    
    # Print to terminal
    print("\n" + "="*60)
    print(f"AUTO-DETECTED VERIFICATION - Type: {material_type}")
    print("="*60)
    print(f"Student Message: {student_message}")
    print(f"Nurse Response: {nurse_response}")
    print(f"Feedback Status: {real_time_feedback.get('status')}")
    print("="*60 + "\n")
    
    staff_nurse_audio = await _safe_tts(nurse_response, role="staff_nurse")
    feedback_audio = await _safe_tts(
        real_time_feedback.get("message", ""),
        role="realtime_feedback",
    )
    return {
        "staff_nurse_response": nurse_response,
        "current_step": session["current_step"],
        "is_verification": True,
        "action_recorded": True,
        "action_type": action_type,
        "timestamp": result.get("timestamp"),
        "staff_nurse_audio": staff_nurse_audio,
        "feedback_audio": feedback_audio,
        "feedback": {
            "message": real_time_feedback.get("message"),
            "status": real_time_feedback.get("status"),
            "can_proceed": real_time_feedback.get("can_proceed")
        }
    }


@router.post("/step")
async def run_step(payload: StepInput):
    """
    Complete current step and get comprehensive feedback.
    
    Flow:
    1. Run evaluator agents (only for HISTORY step)
    2. Aggregate evaluations into scores + raw feedback
    3. Generate narrated feedback paragraph (only for HISTORY step)
    4. Return feedback to client
    5. Advance to next step
    
    When entering CLEANING_AND_DRESSING step, cache RAG guidelines
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
    # Step-specific evaluation
    # ---------------------------------------------
    evaluator_outputs = []

    if current_step == Step.HISTORY.value:
        # Prepare evaluation context
        context = await evaluation_service.prepare_agent_context(
            session_id=payload.session_id,
            step=current_step
        )
        
        # Run both communication and knowledge agents
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
        # ASSESSMENT step uses MCQ-only evaluation (no agents)
        pass

    elif current_step == Step.CLEANING_AND_DRESSING.value:
        # NO FINAL EVALUATION for this step
        pass

    # ---------------------------------------------
    # Print agent feedback to terminal
    # ---------------------------------------------
    if evaluator_outputs:
        print("\n" + "="*80)
        print(f"AGENT EVALUATIONS - Step: {current_step}")
        print("="*80)
        for ev in evaluator_outputs:
            print(f"\n--- {ev.agent_name} ---")
            print(f"Verdict: {ev.verdict} (Confidence: {ev.confidence})")
            print(f"Strengths: {ev.strengths}")
            print(f"Issues: {ev.issues_detected}")
            print(f"Explanation: {ev.explanation}")
        print("="*80 + "\n")

    # ---------------------------------------------
    # Aggregate + narrate feedback
    # ---------------------------------------------
    if current_step == Step.ASSESSMENT.value:
        mcq_answers = session.get("mcq_answers", payload.student_mcq_answers or {})
    else:
        mcq_answers = payload.student_mcq_answers
    
    evaluation = await evaluation_service.aggregate_evaluations(
        session_id=payload.session_id,
        evaluator_outputs=evaluator_outputs,
        student_mcq_answers=mcq_answers,
        student_message_to_nurse=payload.user_input
    )

    # ---------------------------------------------
    # Print final scores to terminal
    # ---------------------------------------------
    if evaluation.get('scores'):
        print("\n" + "="*80)
        print(f"FINAL EVALUATION SCORES - Step: {current_step}")
        print("="*80)
        print(f"Step Quality Indicator: {evaluation.get('scores', {}).get('step_quality_indicator')}")
        print(f"Interpretation: {evaluation.get('scores', {}).get('interpretation')}")
        print(f"Agent Scores: {evaluation.get('scores', {}).get('agent_scores')}")
        print("="*80 + "\n")
    
    if evaluation.get('mcq_result'):
        mcq = evaluation['mcq_result']
        print("\n" + "="*80)
        print(f"MCQ RESULTS - Step: {current_step}")
        print("="*80)
        print(f"Correct: {mcq.get('correct_count')}/{mcq.get('total_questions')}")
        print(f"Score: {mcq.get('score')}")
        print(f"Summary: {mcq.get('summary')}")
        print("="*80 + "\n")

    # ---------------------------------------------
    # Cleanup: Clear step-specific data
    # ---------------------------------------------
    if current_step == Step.HISTORY.value:
        conversation_manager.clear_step(payload.session_id, Step.HISTORY.value)
    
    elif current_step == Step.ASSESSMENT.value:
        session = session_manager.get_session(payload.session_id)
        if session:
            session["mcq_answers"] = {}
    
    elif current_step == Step.CLEANING_AND_DRESSING.value:
        session = session_manager.get_session(payload.session_id)
        if session:
            session["action_events"] = []
            session.pop("cached_rag_guidelines", None)

    # ---------------------------------------------
    # Advance step
    # ---------------------------------------------
    next_step = session_manager.advance_step(payload.session_id)
    
    # Cache RAG guidelines when entering CLEANING_AND_DRESSING step
    if next_step == Step.CLEANING_AND_DRESSING.value:
        print("🔄 Caching RAG guidelines for cleaning_and_dressing step...")
        rag_result = await retrieve_with_rag(
            query="wound cleaning and dressing preparation steps sequence prerequisites required actions",
            scenario_id=session["scenario_id"]
        )
        session["cached_rag_guidelines"] = rag_result.get("text", "")
        print("✓ RAG guidelines cached successfully")

    # ---------------------------------------------
    # Return feedback
    # ---------------------------------------------
    
    if current_step == Step.CLEANING_AND_DRESSING.value:
        completed_count = len(session.get("action_events", []))
        return {
            "session_id": payload.session_id,
            "current_step": current_step,
            "next_step": next_step,
            "summary": {
                "message": "Preparation step completed. Review real-time feedback for details.",
                "actions_completed": completed_count,
                "expected_actions": 9
            }
        }
    
    if current_step == Step.ASSESSMENT.value:
        mcq_result = evaluation.get("mcq_result")
        summary_text = None
        if mcq_result:
            summary_text = (
                f"You answered {mcq_result.get('correct_count')} out of "
                f"{mcq_result.get('total_questions')} questions correctly."
            )
        return {
            "session_id": payload.session_id,
            "current_step": current_step,
            "next_step": next_step,
            "mcq_result": mcq_result,
            "summary_text": summary_text,
            "summary_audio": await _safe_tts(
                summary_text or "",
                role="assessment_feedback",
            ),
        }
    
    return {
        "session_id": payload.session_id,
        "current_step": current_step,
        "next_step": next_step,
        "feedback": {
            "narrated_feedback": evaluation.get("narrated_feedback"),
            "score": evaluation.get("scores", {}).get("step_quality_indicator"),
            "interpretation": evaluation.get("scores", {}).get("interpretation")
        },
        "feedback_audio": await _safe_tts(
            (evaluation.get("narrated_feedback") or {}).get("message_text", ""),
            role="feedback",
        )
    }
