from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ScenarioCreate(BaseModel):
    scenario_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    scenario_data: Dict[str, Any]


class ScenarioUpdate(BaseModel):
    scenario_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    scenario_data: Dict[str, Any]


class ScenarioListItem(BaseModel):
    scenario_id: str
    title: str
    description: str


class UploadResponse(BaseModel):
    message: str
    file_id: str


class ScenarioListResponse(BaseModel):
    scenarios: List[ScenarioListItem]
