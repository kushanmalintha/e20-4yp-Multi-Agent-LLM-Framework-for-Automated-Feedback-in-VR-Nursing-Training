from app.core.state_machine import Step


def test_websocket_connects_with_session_token(client, app_modules, start_session):
    started = start_session()
    session_id = started["session_id"]
    token = started["session_token"]

    with client.websocket_connect(f"/ws/session/{session_id}?token={token}") as websocket:
        message = websocket.receive_json()

    assert message["type"] == "server_event"
    assert message["event"] == "nurse_message"
    assert message["data"]["session_id"] == session_id


def test_websocket_action_event_returns_complete_feedback(client, app_modules, start_session):
    started = start_session()
    session_id = started["session_id"]
    token = started["session_token"]
    session = app_modules.session_routes.session_manager.get_session(session_id)
    session["current_step"] = Step.CLEANING_AND_DRESSING.value
    session["cached_rag_guidelines"] = "guideline text"

    with client.websocket_connect(f"/ws/session/{session_id}?token={token}") as websocket:
        websocket.receive_json()
        websocket.send_json(
            {
                "type": "event",
                "event": "action_performed",
                "data": {"action_type": "action_initial_hand_hygiene"},
            }
        )
        message = websocket.receive_json()

    assert message["type"] == "server_event"
    assert message["event"] == "real_time_feedback"
    assert message["data"]["status"] == "complete"
    assert message["data"]["action_type"] == "action_initial_hand_hygiene"


def test_websocket_invalid_action_sequence_returns_missing_prerequisites(client, app_modules, start_session):
    started = start_session()
    session_id = started["session_id"]
    token = started["session_token"]
    session = app_modules.session_routes.session_manager.get_session(session_id)
    session["current_step"] = Step.CLEANING_AND_DRESSING.value
    session["cached_rag_guidelines"] = "guideline text"

    with client.websocket_connect(f"/ws/session/{session_id}?token={token}") as websocket:
        websocket.receive_json()
        websocket.send_json(
            {
                "type": "event",
                "event": "action_performed",
                "data": {"action_type": "action_clean_trolley"},
            }
        )
        message = websocket.receive_json()

    assert message["type"] == "server_event"
    assert message["event"] == "real_time_feedback"
    assert message["data"]["status"] == "missing_prerequisites"
    assert "action_initial_hand_hygiene" in message["data"]["missing_actions"]

