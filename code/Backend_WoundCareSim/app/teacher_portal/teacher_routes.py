from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.teacher_portal.schemas import ScenarioCreate, ScenarioUpdate
from app.teacher_portal.scenario_service import (
    create_scenario,
    get_scenario,
    list_scenarios,
    update_scenario,
)
from app.teacher_portal.vector_store_service import upload_guideline_file


router = APIRouter(prefix="/teacher", tags=["teacher"])


@router.get("/scenario/list")
async def list_teacher_scenarios():
    return await list_scenarios()


@router.post("/scenario/create", status_code=status.HTTP_201_CREATED)
async def create_teacher_scenario(payload: ScenarioCreate):
    try:
        return await create_scenario(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/scenario/{scenario_id}")
async def get_teacher_scenario(scenario_id: str):
    try:
        return await get_scenario(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scenario/update")
async def update_teacher_scenario(payload: ScenarioUpdate):
    try:
        return await update_scenario(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/vector/upload")
async def upload_guideline(file: UploadFile = File(...)):
    try:
        file_id = await upload_guideline_file(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vector upload failed: {exc}") from exc

    return {
        "message": "File uploaded to vector store",
        "file_id": file_id,
    }
