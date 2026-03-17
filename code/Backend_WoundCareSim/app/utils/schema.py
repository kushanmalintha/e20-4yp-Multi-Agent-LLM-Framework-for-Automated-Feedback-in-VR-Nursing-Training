from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class EvaluatorResponse(BaseModel):
    agent_name: str
    step: str
    strengths: List[str]
    issues_detected: List[str]
    explanation: str
    verdict: str
    confidence: float
    metadata: Optional[Dict[str, Any]] = None
