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
# Step-wise agent importance weights
# --------------------------------------
STEP_WEIGHTS = {
    "history": {
        "CommunicationAgent": 0.4,   # Communication skills
        "KnowledgeAgent": 0.6,        # Information gathering completeness (more critical)
    },
    "assessment": {
        # ASSESSMENT uses MCQ-only evaluation (no agent weights)
        # No evaluator agents run for this step
    },
    "cleaning": {
        "ClinicalAgent": 1.0,  # Only clinical evaluation matters for cleaning
    },
    "dressing": {
        "ClinicalAgent": 1.0,  # Only clinical evaluation matters for dressing
    },
}


def score_single_evaluation(ev: EvaluatorResponse) -> float:
    """
    Convert one evaluator output into a numeric score.

    Scoring logic:
    - Base score from verdict (Appropriate=1.0, Partially=0.6, Inappropriate=0.0)
    - Multiplied by confidence (0.0-1.0)
    
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

    For history-taking:
    - CommunicationAgent score (40% weight)
    - KnowledgeAgent score (60% weight)
    - Composite quality indicator
    
    IMPORTANT:
    - No thresholds
    - No readiness decisions
    - No safety blocking
    - Purely informational for learning feedback
    """

    weights = STEP_WEIGHTS.get(current_step, {})
    agent_scores: Dict[str, float] = {}
    composite_score = 0.0

    # If no evaluations (e.g., ASSESSMENT step), return empty scores
    if not evaluations:
        return {
            "agent_scores": {},
            "step_quality_indicator": 0.0,
        }

    # Calculate individual agent scores
    for ev in evaluations:
        score = score_single_evaluation(ev)
        agent_scores[ev.agent_name] = score

        # Apply weight for composite score
        weight = weights.get(ev.agent_name, 0.0)
        composite_score += score * weight

    return {
        "agent_scores": agent_scores,
        "step_quality_indicator": round(composite_score, 3),
        "interpretation": _interpret_composite_score(composite_score, current_step)
    }


def _interpret_composite_score(score: float, step: str) -> str:
    """
    Provide educational interpretation of the composite score.
    This helps students understand what the score means.
    """
    if step == "history":
        if score >= 0.85:
            return "Excellent history-taking performance"
        elif score >= 0.70:
            return "Good history-taking with minor gaps"
        elif score >= 0.50:
            return "Adequate history-taking with notable areas for improvement"
        else:
            return "History-taking needs significant improvement"
    
    elif step in ["cleaning", "dressing"]:
        if score >= 0.85:
            return "Excellent procedural technique"
        elif score >= 0.70:
            return "Good technique with minor issues"
        elif score >= 0.50:
            return "Adequate technique with safety concerns"
        else:
            return "Procedural technique needs significant improvement"
    
    else:
        return "Performance assessment complete"
