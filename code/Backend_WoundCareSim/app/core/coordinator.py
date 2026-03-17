from typing import List, Dict, Any
from app.utils.schema import EvaluatorResponse
from app.utils.scoring import aggregate_scores


class Coordinator:
    """
    Aggregates evaluator outputs into a unified feedback object.
    """

    def aggregate(
        self,
        evaluations: List[EvaluatorResponse],
        current_step: str
    ) -> Dict[str, Any]:

        if not evaluations:
            return {
                "step": current_step,
                "summary": {
                    "strengths": [],
                    "issues_detected": ["No evaluator outputs received"],
                },
                "agent_feedback": {},
                "combined_explanation": "",
                "scores": {},
            }

        agent_feedback: Dict[str, Any] = {}
        strengths: List[str] = []
        issues: List[str] = []
        explanations: List[str] = []

        for ev in evaluations:
            agent_feedback[ev.agent_name] = {
                "strengths": ev.strengths,
                "issues_detected": ev.issues_detected,
                "explanation": ev.explanation,
                "verdict": ev.verdict,
                "confidence": ev.confidence,
            }

            strengths.extend(
                [f"[{ev.agent_name}] {s}" for s in ev.strengths]
            )
            issues.extend(
                [f"[{ev.agent_name}] {i}" for i in ev.issues_detected]
            )
            explanations.append(
                f"[{ev.agent_name}] {ev.explanation}"
            )

        # Informational scoring only (no thresholds, no blocking)
        scores = aggregate_scores(evaluations, current_step)

        return {
            "step": current_step,
            "summary": {
                "strengths": strengths,
                "issues_detected": issues,
            },
            "agent_feedback": agent_feedback,
            "combined_explanation": " ".join(explanations),
            "scores": scores,
        }
