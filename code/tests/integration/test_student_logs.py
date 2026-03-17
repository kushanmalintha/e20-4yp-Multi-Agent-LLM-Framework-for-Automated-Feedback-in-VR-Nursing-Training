from app.core.state_machine import Step


def test_session_log_contains_all_step_sections(client, app_modules, start_session):
    started = start_session()
    session_id = started["session_id"]
    session = app_modules.session_routes.session_manager.get_session(session_id)

    app_modules.session_routes.conversation_manager.add_turn(
        session_id, Step.HISTORY.value, "student", "I checked your identity and allergies."
    )
    app_modules.session_routes.conversation_manager.add_turn(
        session_id, Step.HISTORY.value, "patient", "Thank you."
    )
    session["mcq_answers"] = {
        "q1": "Surgical wound",
        "q2": "Left forearm",
    }
    session["action_events"] = [
        {"action_type": "action_initial_hand_hygiene", "timestamp": "2026-03-13T00:00:00"},
        {"action_type": "action_clean_trolley", "timestamp": "2026-03-13T00:01:00"},
        {"action_type": "action_hand_hygiene_after_cleaning", "timestamp": "2026-03-13T00:02:00"},
    ]
    session["current_step"] = "completed"

    response = client.get(f"/session/{session_id}/log")

    assert response.status_code == 200
    payload = response.json()
    assert "steps" in payload
    assert "history" in payload["steps"]
    assert "assessment" in payload["steps"]
    assert "cleaning_and_dressing" in payload["steps"]
