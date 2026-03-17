from unittest.mock import AsyncMock

import pytest

from app.agents.clinical_agent import ClinicalAgent


@pytest.mark.asyncio
async def test_missing_prerequisites_returns_missing_status(monkeypatch):
    agent = ClinicalAgent()
    explain_mock = AsyncMock(return_value="Missing prerequisite explanation")
    monkeypatch.setattr(agent, "_explain_missing_prerequisites", explain_mock)

    result = await agent.get_real_time_feedback(
        action_type="action_verify_solution",
        performed_actions=[],
        rag_guidelines="guidelines",
    )

    assert result["status"] == "missing_prerequisites"
    assert result["can_proceed"] is False
    assert "action_initial_hand_hygiene" in result["missing_actions"]
    assert result["message"] == "Missing prerequisite explanation"
    explain_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_correct_prerequisites_returns_complete(monkeypatch):
    agent = ClinicalAgent()
    run_mock = AsyncMock(side_effect=AssertionError("LLM path should not be called"))
    monkeypatch.setattr(agent, "run", run_mock)

    performed_actions = [
        {"action_type": "action_initial_hand_hygiene"},
        {"action_type": "action_clean_trolley"},
        {"action_type": "action_hand_hygiene_after_cleaning"},
        {"action_type": "action_select_solution"},
    ]

    result = await agent.get_real_time_feedback(
        action_type="action_verify_solution",
        performed_actions=performed_actions,
    )

    assert result["status"] == "complete"
    assert result["can_proceed"] is True
    assert result["missing_actions"] == []
    assert "Done correctly" in result["message"]
    run_mock.assert_not_called()


@pytest.mark.asyncio
async def test_partial_prerequisites_returns_specific_missing_action(monkeypatch):
    agent = ClinicalAgent()
    explain_mock = AsyncMock(return_value="One prerequisite is still missing")
    monkeypatch.setattr(agent, "_explain_missing_prerequisites", explain_mock)

    performed_actions = [
        {"action_type": "action_initial_hand_hygiene"},
        {"action_type": "action_clean_trolley"},
        {"action_type": "action_hand_hygiene_after_cleaning"},
        {"action_type": "action_select_solution"},
        # Missing action_verify_solution
        {"action_type": "action_select_dressing"},
    ]

    result = await agent.get_real_time_feedback(
        action_type="action_verify_dressing",
        performed_actions=performed_actions,
        rag_guidelines="guidelines",
    )

    assert result["status"] == "missing_prerequisites"
    assert result["missing_actions"] == ["action_verify_solution"]
    assert result["message"] == "One prerequisite is still missing"
    explain_mock.assert_awaited_once()
