from typing import List, Dict
from app.utils.schema import EvaluatorResponse


HISTORY_RUBRIC_BASE = {
    "identity_asked":        0.15,
    "allergies_asked":       0.25,
    "pain_assessed":         0.20,
    "medical_history_asked": 0.20,
    "procedure_explained":   0.10,
    "risk_factor_assessed":  0.10,
}

HISTORY_RUBRIC_NO_RISK = {
    "identity_asked":        0.15,
    "allergies_asked":       0.30,
    "pain_assessed":         0.20,
    "medical_history_asked": 0.20,
    "procedure_explained":   0.15,
}


def aggregate_scores(
    evaluations: List[EvaluatorResponse],
    current_step: str,
    clinical_context: dict = None,
) -> Dict[str, float]:

    if current_step != "history" or not evaluations:
        return {
            "agent_scores": {},
            "step_quality_indicator": None,
        }

    clinical_context = clinical_context or {}
    risk_factors = clinical_context.get("risk_factors", [])
    has_risk_factors = bool(risk_factors)

    rubric = HISTORY_RUBRIC_BASE if has_risk_factors else HISTORY_RUBRIC_NO_RISK

    agent_scores = {}
    composite_score = 0.0

    for ev in evaluations:
        if ev.agent_name == "KnowledgeAgent":
            flags = ev.metadata or {}
            score = 0.0
            for key, weight in rubric.items():
                if flags.get(key):
                    score += weight

            agent_scores["KnowledgeAgent"] = round(score, 3)
            composite_score += score * 0.6

        elif ev.agent_name == "CommunicationAgent":
            comm_score = 1.0 if ev.verdict == "Appropriate" else \
                         0.5 if ev.verdict == "Partially Appropriate" else 0.0

            agent_scores["CommunicationAgent"] = comm_score
            composite_score += comm_score * 0.4

    return {
        "agent_scores": agent_scores,
        "step_quality_indicator": round(composite_score, 3),
        "interpretation": _interpret_score(composite_score)
    }


def _interpret_score(score: float) -> str:
    if score >= 0.85:
        return "Excellent history-taking performance"
    elif score >= 0.70:
        return "Good history-taking with minor gaps"
    elif score >= 0.50:
        return "Adequate history-taking with notable improvement areas"
    else:
        return "History-taking requires significant improvement"
