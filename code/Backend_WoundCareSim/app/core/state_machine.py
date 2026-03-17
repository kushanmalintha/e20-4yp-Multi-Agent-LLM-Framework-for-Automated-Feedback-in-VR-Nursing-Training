from enum import Enum

class Step(Enum):
    HISTORY = "history"
    ASSESSMENT = "assessment"
    CLEANING_AND_DRESSING = "cleaning_and_dressing"
    COMPLETED = "completed"

# valid forward transitions
_VALID_TRANSITIONS = {
    Step.HISTORY: Step.ASSESSMENT,
    Step.ASSESSMENT: Step.CLEANING_AND_DRESSING,
    Step.CLEANING_AND_DRESSING: Step.COMPLETED,
}

def next_step(current_step: Step):
    """Return the next step or raise ValueError if none."""
    if current_step not in _VALID_TRANSITIONS:
        raise ValueError(f"No next step for {current_step}")
    return _VALID_TRANSITIONS[current_step]

def validate_action(step: Step, event_type: str) -> bool:
    """
    Validates if an action type is allowed for the given step.
    
    Note: Specific action requirements come from RAG guidelines.
    This just validates the action belongs to the right step category.
    """
    mapping = {
        Step.HISTORY: {"voice_transcript", "question_asked"},
        Step.ASSESSMENT: {"mcq_answer", "visual_assessment"},
        Step.CLEANING_AND_DRESSING: {
            # Any action starting with "action_" is allowed
            # Specific actions are defined in RAG guidelines
            # Frontend/VR will determine valid actions based on RAG
        },
        Step.COMPLETED: set(),
    }
    
    allowed = mapping.get(step, set())
    
    # For CLEANING_AND_DRESSING, allow any action_ prefixed event
    if step == Step.CLEANING_AND_DRESSING and event_type.startswith("action_"):
        return True
    
    return event_type in allowed
