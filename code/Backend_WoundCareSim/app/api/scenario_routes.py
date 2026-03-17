from fastapi import APIRouter, HTTPException
from typing import Dict, List
from app.services.scenario_service import (
    create_scenario,
    update_scenario,
    delete_scenario,
    get_scenario,
    list_scenarios
)

router = APIRouter(prefix="/scenario", tags=["Scenario"])


@router.post("/create")
def create(data: Dict):
    try:
        return create_scenario(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/update/{scenario_id}")
def update(scenario_id: str, data: Dict):
    try:
        return update_scenario(scenario_id, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/delete/{scenario_id}")
def delete(scenario_id: str):
    try:
        return delete_scenario(scenario_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/list")
def list_all() -> List[Dict]:
    return list_scenarios()


@router.get("/{scenario_id}")
def get(scenario_id: str):
    try:
        return get_scenario(scenario_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
