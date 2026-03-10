import json
from pathlib import Path

from app.utils.firebase_client import create_scenario_metadata
from app.services.student_log_service import StudentLogService

BASE_DIR = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------
# Scenario upload
# ------------------------------------------------------------------

def upload_scenario(json_path: Path):
    """Upload a scenario JSON file to Firestore under the 'scenarios' collection."""
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    scenario_id = payload["scenario_id"]
    create_scenario_metadata(scenario_id, payload)

    print(f"Scenario '{scenario_id}' uploaded successfully.")


# ------------------------------------------------------------------
# Student log upload  (Firestore only)
# ------------------------------------------------------------------

def save_student_log_to_firestore(log: dict) -> str:
    firestore_path = StudentLogService.save_to_firestore(log)
    print(f"[LOG] Student log saved to Firestore -> {firestore_path}")
    return firestore_path


# ------------------------------------------------------------------
# Entry point (scenario upload only)
# ------------------------------------------------------------------

if __name__ == "__main__":
    json_file = BASE_DIR / "data" / "scenario.json"
    upload_scenario(json_file)
