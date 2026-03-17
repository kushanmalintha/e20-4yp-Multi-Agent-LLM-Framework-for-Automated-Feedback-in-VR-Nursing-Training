from app.agents.communication_agent import CommunicationAgent


def test_parse_response_accepts_python_like_dict_string():
    agent = CommunicationAgent()
    raw_response = """{
        'strengths': ['Polite introduction'],
        'issues_detected': [],
        'explanation': 'Good communication overall.',
        'verdict': 'Appropriate',
        'confidence': 0.9
    }"""

    result = agent._parse_response(raw_response, "history", "student: Hello, I am your nurse.")

    assert result.verdict == "Appropriate"
    assert result.confidence == 0.9
    assert result.strengths == ["Polite introduction"]


def test_parse_response_uses_heuristic_fallback_when_unparseable():
    agent = CommunicationAgent()
    student_input = "\n".join(
        [
            "student: Hello, I am your nurse today.",
            "student: Could you confirm your name for me?",
            "student: I will explain the procedure before we begin.",
        ]
    )

    result = agent._parse_response("not valid json", "history", student_input)

    assert result.verdict == "Appropriate"
    assert result.confidence == 0.35
    assert "Fallback heuristic" in result.explanation


def test_heuristic_fallback_marks_abrupt_tone_inappropriate():
    agent = CommunicationAgent()
    student_input = "\n".join(
        [
            "student: State your name.",
            "student: Answer quickly.",
        ]
    )

    result = agent._heuristic_fallback("history", student_input)

    assert result.verdict == "Inappropriate"
    assert "Tone included abrupt or pressuring language" in result.issues_detected
