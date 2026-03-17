from typing import Dict, List, Any


class MCQEvaluator:
    """
    Educational MCQ evaluator for ASSESSMENT step.

    Principles:
    - No blocking
    - No retries
    - No pass/fail
    - Always returns feedback
    """

    @staticmethod
    def validate_mcq_answers(
        student_answers: Dict[str, str],
        assessment_questions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:

        if not assessment_questions:
            return {
                "total_questions": 0,
                "correct_count": 0,
                "score": 0.0,
                "feedback": [],
                "summary": "No MCQ questions available"
            }

        feedback = []
        correct_count = 0

        for q in assessment_questions:
            qid = q.get("id")
            question_text = q.get("question", "")
            correct_answer = q.get("correct_answer")
            explanation = q.get("explanation", "No explanation provided.")

            student_answer = student_answers.get(qid)

            if student_answer == correct_answer:
                correct_count += 1
                feedback.append({
                    "question_id": qid,
                    "question": question_text,
                    "status": "correct",
                    "student_answer": student_answer,
                    "correct_answer": correct_answer,
                    "explanation": explanation
                })
            else:
                feedback.append({
                    "question_id": qid,
                    "question": question_text,
                    "status": "incorrect",
                    "student_answer": student_answer,
                    "correct_answer": correct_answer,
                    "explanation": explanation
                })

        total = len(assessment_questions)
        score = correct_count / total if total > 0 else 0.0

        return {
            "total_questions": total,
            "correct_count": correct_count,
            "score": round(score, 2),
            "feedback": feedback,
            "summary": f"{correct_count}/{total} questions answered correctly"
        }
