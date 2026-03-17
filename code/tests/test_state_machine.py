import pytest

from app.core.state_machine import Step, next_step, validate_action


@pytest.mark.parametrize(
    ("current_step", "expected_next"),
    [
        (Step.HISTORY, Step.ASSESSMENT),
        (Step.ASSESSMENT, Step.CLEANING_AND_DRESSING),
        (Step.CLEANING_AND_DRESSING, Step.COMPLETED),
    ],
)
def test_next_step_valid_transitions(current_step, expected_next):
    assert next_step(current_step) is expected_next


def test_next_step_completed_raises_value_error():
    with pytest.raises(ValueError, match="No next step"):
        next_step(Step.COMPLETED)


def test_validate_action_allows_history_events():
    assert validate_action(Step.HISTORY, "voice_transcript") is True
    assert validate_action(Step.HISTORY, "mcq_answer") is False


def test_validate_action_allows_cleaning_action_prefix_only():
    assert validate_action(Step.CLEANING_AND_DRESSING, "action_verify_solution") is True
    assert validate_action(Step.CLEANING_AND_DRESSING, "voice_transcript") is False

