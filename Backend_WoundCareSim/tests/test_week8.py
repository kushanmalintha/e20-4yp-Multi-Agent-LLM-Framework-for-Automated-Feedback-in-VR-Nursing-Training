import asyncio
import json
from datetime import datetime
from pathlib import Path

from app.core.coordinator import Coordinator
from app.services.evaluation_service import EvaluationService
from app.services.session_manager import SessionManager
from app.services.action_event_service import ActionEventService

from app.agents.communication_agent import CommunicationAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.clinical_agent import ClinicalAgent
from app.agents.patient_agent import PatientAgent
from app.agents.staff_nurse_agent import StaffNurseAgent


LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


async def run_full_system_test():
    """
    Manual end-to-end system validation (Week-8).

    EXPECTATIONS:
    - Each evaluator agent produces visible feedback
    - Feedback text is non-empty
    - Coordinator provides scores only
    - Staff nurse provides optional guidance
    """

    scenario_id = "week6_mock_scenario"
    student_id = "manual_test_student"

    session_manager = SessionManager()
    coordinator = Coordinator()
    staff_nurse_agent = StaffNurseAgent()

    evaluation_service = EvaluationService(
        coordinator=coordinator,
        session_manager=session_manager,
        staff_nurse_agent=staff_nurse_agent
    )

    action_service = ActionEventService(session_manager)
    patient_agent = PatientAgent()

    agents = [
        CommunicationAgent(),
        KnowledgeAgent(),
        ClinicalAgent()
    ]

    session_id = session_manager.create_session(
        scenario_id=scenario_id,
        student_id=student_id
    )

    scenario_meta = session_manager.get_session(session_id)["scenario_metadata"]
    patient_history = scenario_meta.get("patient_history", {})

    log = {
        "scenario_id": scenario_id,
        "student_id": student_id,
        "steps": []
    }

    # ==============================
    # HISTORY
    # ==============================
    print("\n===== HISTORY =====")

    conversation = [
        "Hello, I am a nursing student. Can you confirm your name?",
        "Do you have any allergies?",
        "Can you tell me about the surgery you had?"
    ]

    for msg in conversation:
        evaluation_service.conversation_manager.add_turn(
            session_id, "history", "student", msg
        )

        patient_response = await patient_agent.respond(
            patient_history=patient_history,
            conversation_history=evaluation_service.conversation_manager.conversations[
                session_id
            ]["history"],
            student_message=msg
        )

        evaluation_service.conversation_manager.add_turn(
            session_id, "history", "patient", patient_response
        )

    context = await evaluation_service.prepare_agent_context(
        session_id=session_id,
        step="history"
    )

    evaluator_outputs = [
        await agent.evaluate(
            current_step="history",
            student_input=context["transcript"],
            scenario_metadata=context["scenario_metadata"],
            rag_response=context["rag_context"]
        )
        for agent in agents
    ]

    aggregated = await evaluation_service.aggregate_evaluations(
        session_id=session_id,
        evaluator_outputs=evaluator_outputs,
        student_message_to_nurse="I think I am done. What should I do next?"
    )

    print("\n--- FEEDBACK OUTPUTS ---")
    for fb in aggregated["feedback"]:
        print(f"[{fb['speaker'].upper()} | {fb['category']}]\n{fb['text']}\n")
        assert fb["text"].strip() != ""

    print("--- SCORES ---")
    print(aggregated["scores"])

    log["steps"].append({
        "step": "history",
        "feedback": aggregated
    })

    # ==============================
    # ASSESSMENT
    # ==============================
    print("\n===== ASSESSMENT =====")

    student_mcq_answers = {
        "q1": "Remove the old dressing",
        "q2": "Dry wound surface"
    }

    context = await evaluation_service.prepare_agent_context(
        session_id=session_id,
        step="assessment"
    )

    evaluator_outputs = [
        await agent.evaluate(
            current_step="assessment",
            student_input="Assessment completed.",
            scenario_metadata=context["scenario_metadata"],
            rag_response=context["rag_context"]
        )
        for agent in agents
    ]

    aggregated = await evaluation_service.aggregate_evaluations(
        session_id=session_id,
        evaluator_outputs=evaluator_outputs,
        student_mcq_answers=student_mcq_answers
    )

    print("\n--- FEEDBACK OUTPUTS ---")
    for fb in aggregated["feedback"]:
        print(f"[{fb['speaker'].upper()} | {fb['category']}]\n{fb['text']}\n")
        assert fb["text"].strip() != ""

    log["steps"].append({
        "step": "assessment",
        "feedback": aggregated
    })

    # ==============================
    # CLEANING & DRESSING (brief)
    # ==============================
    for step, actions in {
        "cleaning": ["SKIP_HAND_WASH", "CLEAN_WOUND"],
        "dressing": ["APPLY_DRESSING", "SECURE_BANDAGE"]
    }.items():

        print(f"\n===== {step.upper()} =====")

        for act in actions:
            action_service.record_action(session_id, act, step)

        context = await evaluation_service.prepare_agent_context(
            session_id=session_id,
            step=step
        )

        evaluator_outputs = [
            await agent.evaluate(
                current_step=step,
                student_input="",
                scenario_metadata=context["scenario_metadata"],
                rag_response=context["rag_context"]
            )
            for agent in agents
        ]

        aggregated = await evaluation_service.aggregate_evaluations(
            session_id=session_id,
            evaluator_outputs=evaluator_outputs
        )

        for fb in aggregated["feedback"]:
            print(f"[{fb['speaker'].upper()} | {fb['category']}]\n{fb['text']}\n")
            assert fb["text"].strip() != ""

        log["steps"].append({
            "step": step,
            "feedback": aggregated
        })

    log_path = LOG_DIR / f"manual_test_week8_{session_id}.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

    print("\n✅ WEEK-8 TEST PASSED")
    print(f"Log saved to {log_path}")


if __name__ == "__main__":
    asyncio.run(run_full_system_test())
