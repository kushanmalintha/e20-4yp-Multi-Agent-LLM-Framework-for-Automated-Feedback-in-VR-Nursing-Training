from typing import List, Dict
from app.utils.schema import EvaluatorResponse


# --------------------------------------
# Verdict → Base score mapping
# --------------------------------------
VERDICT_SCORE_MAP = {
    "Appropriate": 1.0,
    "Partially Appropriate": 0.6,
    "Inappropriate": 0.0,
}


# --------------------------------------
# Step-wise agent importance (informational)
# --------------------------------------
STEP_WEIGHTS = {
    "history": {
        "CommunicationAgent": 0.5,
        "KnowledgeAgent": 0.4,
        "ClinicalAgent": 0.1,
    },
    "assessment": {
        "CommunicationAgent": 0.3,
        "KnowledgeAgent": 0.7,
        "ClinicalAgent": 0.0,
    },
    "cleaning": {
        "CommunicationAgent": 0.1,
        "KnowledgeAgent": 0.1,
        "ClinicalAgent": 0.8,
    },
    "dressing": {
        "CommunicationAgent": 0.1,
        "KnowledgeAgent": 0.1,
        "ClinicalAgent": 0.8,
    },
}


def score_single_evaluation(ev: EvaluatorResponse) -> float:
    """
    Convert one evaluator output into a numeric score.

    NOTE:
    Scores are informational only (feedback, reporting).
    They do NOT control progression or blocking.
    """
    base_score = VERDICT_SCORE_MAP.get(ev.verdict, 0.0)
    return round(base_score * ev.confidence, 3)


def aggregate_scores(
    evaluations: List[EvaluatorResponse],
    current_step: str
) -> Dict[str, float]:
    """
    Compute per-agent and composite scores for feedback purposes.

    IMPORTANT:
    - No thresholds
    - No readiness decisions
    - No safety blocking
    """

    weights = STEP_WEIGHTS.get(current_step, {})
    agent_scores: Dict[str, float] = {}
    composite_score = 0.0

    for ev in evaluations:
        score = score_single_evaluation(ev)
        agent_scores[ev.agent_name] = score

        weight = weights.get(ev.agent_name, 0.0)
        composite_score += score * weight

    return {
        "agent_scores": agent_scores,
        "step_quality_indicator": round(composite_score, 3),
    }
