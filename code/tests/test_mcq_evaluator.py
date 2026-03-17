import pytest

from app.utils.mcq_evaluator import MCQEvaluator


QUESTIONS = [
    {
        "id": "q1",
        "question": "Question 1",
        "correct_answer": "A",
        "explanation": "Explanation 1",
    },
    {
        "id": "q2",
        "question": "Question 2",
        "correct_answer": "B",
        "explanation": "Explanation 2",
    },
    {
        "id": "q3",
        "question": "Question 3",
        "correct_answer": "C",
        "explanation": "Explanation 3",
    },
]


@pytest.mark.parametrize(
    ("student_answers", "expected_correct", "expected_score", "expected_statuses"),
    [
        ({"q1": "A", "q2": "B", "q3": "C"}, 3, 1.0, ["correct", "correct", "correct"]),
        ({"q1": "X", "q2": "Y", "q3": "Z"}, 0, 0.0, ["incorrect", "incorrect", "incorrect"]),
        ({"q1": "A", "q2": "Y", "q3": "C"}, 2, 0.67, ["correct", "incorrect", "correct"]),
        ({}, 0, 0.0, ["incorrect", "incorrect", "incorrect"]),
    ],
)
def test_validate_mcq_answers_cases(
    student_answers, expected_correct, expected_score, expected_statuses
):
    result = MCQEvaluator.validate_mcq_answers(student_answers, QUESTIONS)

    assert result["correct_count"] == expected_correct
    assert result["score"] == expected_score
    assert [item["status"] for item in result["feedback"]] == expected_statuses


def test_validate_mcq_answers_handles_missing_correct_answer_field():
    questions = [
        {
            "id": "q1",
            "question": "Question without answer",
            "explanation": "Fallback explanation",
        }
    ]

    result = MCQEvaluator.validate_mcq_answers({"q1": "A"}, questions)

    assert result["correct_count"] == 0
    assert result["score"] == 0.0
    assert result["feedback"][0]["status"] == "incorrect"
    assert result["feedback"][0]["correct_answer"] is None


def test_validate_mcq_answers_handles_no_questions():
    result = MCQEvaluator.validate_mcq_answers({}, [])

    assert result["correct_count"] == 0
    assert result["score"] == 0.0
    assert result["feedback"] == []
    assert result["summary"] == "No MCQ questions available"

