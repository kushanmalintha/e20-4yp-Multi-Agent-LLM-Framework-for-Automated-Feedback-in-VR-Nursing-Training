from datetime import datetime
from typing import Any, Dict, List

from app.services.scenario_service import get_scenario as get_existing_scenario
from app.utils.firebase_client import get_document, get_firestore_client
from app.utils.validators import validate_scenario_payload


COLLECTION = "scenarios"


def _normalize_scenario_document(
    scenario_id: str,
    title: str,
    description: str,
    scenario_data: Dict[str, Any],
    existing: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    normalized = dict(scenario_data)
    normalized["scenario_id"] = scenario_id
    normalized["title"] = title
    normalized["description"] = description

    # Preserve runtime compatibility with the existing session loader.
    normalized["scenario_title"] = normalized.get("scenario_title") or title
    normalized["vector_store_namespace"] = (
        normalized.get("vector_store_namespace") or scenario_id
    )
    normalized["evaluation_criteria"] = normalized.get("evaluation_criteria") or {}
    normalized["created_at"] = (
        normalized.get("created_at")
        or (existing or {}).get("created_at")
        or datetime.utcnow().isoformat()
    )
    normalized["updated_at"] = datetime.utcnow().isoformat()

    validate_scenario_payload(normalized)
    return normalized


async def create_scenario(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _normalize_scenario_document(
        scenario_id=payload["scenario_id"],
        title=payload["title"],
        description=payload["description"],
        scenario_data=payload["scenario_data"],
    )

    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION).document(payload["scenario_id"])
    if doc_ref.get().exists:
        raise ValueError(f"Scenario '{payload['scenario_id']}' already exists")

    doc_ref.set(normalized)
    return {
        "message": "Scenario created successfully",
        "scenario_id": payload["scenario_id"],
    }


async def update_scenario(payload: Dict[str, Any]) -> Dict[str, Any]:
    db = get_firestore_client()
    doc_ref = db.collection(COLLECTION).document(payload["scenario_id"])
    existing_snapshot = doc_ref.get()
    if not existing_snapshot.exists:
        raise ValueError(f"Scenario '{payload['scenario_id']}' does not exist")

    existing = existing_snapshot.to_dict() or {}
    normalized = _normalize_scenario_document(
        scenario_id=payload["scenario_id"],
        title=payload["title"],
        description=payload["description"],
        scenario_data=payload["scenario_data"],
        existing=existing,
    )
    doc_ref.set(normalized)
    return {
        "message": "Scenario updated successfully",
        "scenario_id": payload["scenario_id"],
    }


async def list_scenarios() -> List[Dict[str, str]]:
    db = get_firestore_client()
    docs = db.collection(COLLECTION).stream()
    scenarios: List[Dict[str, str]] = []

    for doc in docs:
        data = doc.to_dict() or {}
        scenarios.append(
            {
                "scenario_id": data.get("scenario_id", doc.id),
                "title": data.get("title") or data.get("scenario_title") or doc.id,
                "description": data.get("description") or "",
            }
        )

    scenarios.sort(key=lambda item: item["scenario_id"])
    return scenarios


async def get_scenario(scenario_id: str) -> Dict[str, Any]:
    scenario = get_document(COLLECTION, scenario_id)
    if not scenario:
        raise ValueError("Scenario not found")

    # Validate that this remains usable by the runtime before returning it.
    validate_scenario_payload(
        {
            **scenario,
            "scenario_title": scenario.get("scenario_title")
            or scenario.get("title")
            or scenario_id,
            "vector_store_namespace": scenario.get("vector_store_namespace") or scenario_id,
        }
    )
    return scenario


async def get_runtime_scenario(scenario_id: str) -> Dict[str, Any]:
    return get_existing_scenario(scenario_id)
