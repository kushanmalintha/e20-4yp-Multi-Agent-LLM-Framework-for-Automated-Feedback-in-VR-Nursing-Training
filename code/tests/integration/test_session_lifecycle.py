def test_session_lifecycle_start_active_and_fetch(client, start_session):
    started = start_session()
    session_id = started["session_id"]

    active_response = client.get("/session/active")
    session_response = client.get(f"/session/{session_id}")

    assert active_response.status_code == 200
    assert session_response.status_code == 200

    active_payload = active_response.json()
    session_payload = session_response.json()

    assert started["session_id"]
    assert started["session_token"]
    assert active_payload["session_id"] == session_id
    assert active_payload["session_token"] == started["session_token"]
    assert session_payload["session_id"] == session_id
    assert session_payload["session_token"] == started["session_token"]
    assert session_payload["current_step"] == "history"

