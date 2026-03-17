from app.utils.schema import EvaluatorResponse
from app.utils.scoring import aggregate_scores


def make_knowledge_response(**flags):
    return EvaluatorResponse(
        agent_name="KnowledgeAgent",
        step="history",
        strengths=[],
        issues_detected=[],
        explanation="",
        verdict="Evaluated",
        confidence=1.0,
        metadata=flags,
    )


def make_communication_response(verdict):
    return EvaluatorResponse(
        agent_name="CommunicationAgent",
        step="history",
        strengths=[],
        issues_detected=[],
        explanation="",
        verdict=verdict,
        confidence=1.0,
        metadata=None,
    )


def test_aggregate_scores_all_flags_true_and_appropriate_is_high():
    evaluations = [
        make_knowledge_response(
            identity_asked=True,
            allergies_asked=True,
            pain_assessed=True,
            medical_history_asked=True,
            procedure_explained=True,
            risk_factor_assessed=True,
        ),
        make_communication_response("Appropriate"),
    ]

    result = aggregate_scores(
        evaluations,
        current_step="history",
        clinical_context={"risk_factors": ["diabetes"]},
    )

    assert result["agent_scores"]["KnowledgeAgent"] == 1.0
    assert result["agent_scores"]["CommunicationAgent"] == 1.0
    assert result["step_quality_indicator"] >= 0.85


def test_aggregate_scores_all_flags_false_is_near_zero():
    evaluations = [
        make_knowledge_response(
            identity_asked=False,
            allergies_asked=False,
            pain_assessed=False,
            medical_history_asked=False,
            procedure_explained=False,
            risk_factor_assessed=False,
        ),
        make_communication_response("Inappropriate"),
    ]

    result = aggregate_scores(evaluations, current_step="history", clinical_context={})

    assert result["agent_scores"]["KnowledgeAgent"] == 0.0
    assert result["agent_scores"]["CommunicationAgent"] == 0.0
    assert result["step_quality_indicator"] == 0.0


def test_aggregate_scores_applies_diabetes_risk_factor_weight():
    evaluations = [
        make_knowledge_response(risk_factor_assessed=True),
        make_communication_response("Inappropriate"),
    ]

    with_diabetes = aggregate_scores(
        evaluations,
        current_step="history",
        clinical_context={"risk_factors": ["diabetes"]},
    )
    without_diabetes = aggregate_scores(
        evaluations,
        current_step="history",
        clinical_context={},
    )

    assert with_diabetes["agent_scores"]["KnowledgeAgent"] == 0.1
    assert with_diabetes["step_quality_indicator"] == 0.06
    assert without_diabetes["agent_scores"]["KnowledgeAgent"] == 0.0
    assert without_diabetes["step_quality_indicator"] == 0.0


def test_aggregate_scores_returns_empty_for_non_history_step():
    result = aggregate_scores([], current_step="assessment", clinical_context={})

    assert result == {"agent_scores": {}, "step_quality_indicator": None}

