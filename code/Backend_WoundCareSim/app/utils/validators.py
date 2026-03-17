from typing import Dict, Any, List

# -------------------------------
# Scenario Validation
# -------------------------------

REQUIRED_SCENARIO_FIELDS = [
    "scenario_id",
    "scenario_title",
    "patient_history",
    "wound_details",
    "assessment_questions",
    "vector_store_namespace"
]


def validate_scenario_payload(data: Dict[str, Any]) -> None:
    """
    Validates scenario metadata before storing or loading.
    Core validation: patient context + MCQ questions only
    """
    missing = [f for f in REQUIRED_SCENARIO_FIELDS if f not in data]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    if not isinstance(data["assessment_questions"], list):
        raise ValueError("assessment_questions must be a list")

    validate_mcq_list(data["assessment_questions"])


# -------------------------------
# MCQ Validation
# -------------------------------

def validate_mcq_list(mcqs: List[Dict[str, Any]]) -> None:
    if not mcqs:
        raise ValueError("assessment_questions cannot be empty")

    for i, mcq in enumerate(mcqs):
        validate_mcq(mcq, i)


def validate_mcq(mcq: Dict[str, Any], index: int) -> None:
    required = ["question", "options", "correct_answer"]

    for field in required:
        if field not in mcq:
            raise ValueError(f"MCQ {index+1} missing '{field}'")

    if not isinstance(mcq["options"], list) or len(mcq["options"]) < 2:
        raise ValueError(f"MCQ {index+1} must have at least 2 options")

    if not mcq["question"].strip():
        raise ValueError(f"MCQ {index+1} question cannot be empty")

    if not mcq["correct_answer"].strip():
        raise ValueError(f"MCQ {index+1} correct_answer cannot be empty")
