def test_health_endpoint_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_scenario_list_endpoint_returns_expected_schema(client):
    response = client.get("/scenario/list")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload[0]["scenario_id"] == "scenario_001"
    assert "scenario_title" in payload[0]


def test_session_info_endpoint_returns_expected_fields(client, start_session):
    started = start_session()

    response = client.get(f"/session/{started['session_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == started["session_id"]
    assert payload["scenario_id"] == "scenario_001"
    assert payload["student_id"] == "student_001"
    assert payload["current_step"] == "history"
    assert "session_token" in payload
    assert "scenario_metadata" in payload

