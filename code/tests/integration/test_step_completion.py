from app.core.state_machine import Step


def test_complete_history_step_returns_narrated_feedback_and_scores(client, app_modules, start_session):
    started = start_session()
    session_id = started["session_id"]

    app_modules.session_routes.conversation_manager.add_turn(
        session_id, Step.HISTORY.value, "student", "Hello, I am here to assess you."
    )
    app_modules.session_routes.conversation_manager.add_turn(
        session_id, Step.HISTORY.value, "patient", "My wound hurts a little."
    )

    response = client.post(
        "/session/complete-step",
        json={"session_id": session_id, "step": "history"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["feedback_type"] == "history"
    assert payload["feedback"]["narrated_feedback"]["message_text"] == "Narrated history feedback"
    assert payload["feedback"]["score"] >= 0.85
    assert payload["next_step"] == "assessment"


def test_complete_assessment_step_returns_mcq_result(client, app_modules, start_session):
    started = start_session()
    session_id = started["session_id"]
    session = app_modules.session_routes.session_manager.get_session(session_id)
    session["current_step"] = "assessment"
    session["mcq_answers"] = {
        "q1": "Surgical wound",
        "q2": "Right leg",
    }

    response = client.post(
        "/session/complete-step",
        json={"session_id": session_id, "step": "assessment"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["feedback_type"] == "assessment"
    assert payload["feedback"]["mcq_result"]["correct_count"] == 1
    assert payload["feedback"]["mcq_result"]["score"] == 0.5
    assert payload["next_step"] == "cleaning_and_dressing"


def test_complete_cleaning_step_advances_to_completed(client, app_modules, start_session):
    started = start_session()
    session_id = started["session_id"]
    session = app_modules.session_routes.session_manager.get_session(session_id)
    session["current_step"] = "cleaning_and_dressing"
    session["action_events"] = [
        {"action_type": "action_initial_hand_hygiene", "timestamp": "2026-03-13T00:00:00"},
        {"action_type": "action_clean_trolley", "timestamp": "2026-03-13T00:01:00"},
    ]

    response = client.post(
        "/session/complete-step",
        json={"session_id": session_id, "step": "cleaning_and_dressing"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["feedback_type"] == "cleaning_and_dressing"
    assert payload["next_step"] == "completed"
    assert payload["session_end"] is True

