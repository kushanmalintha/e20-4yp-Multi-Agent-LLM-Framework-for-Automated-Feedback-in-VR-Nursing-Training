import os
import firebase_admin
from firebase_admin import credentials, firestore

from dotenv import load_dotenv
load_dotenv()

FIREBASE_SA = "../../fyp-woundcaresim-firebase-adminsdk-fbsvc-ec03499240.json"
if not FIREBASE_SA:
    raise RuntimeError("FIREBASE_SERVICE_ACCOUNT env var not set (path to service account JSON)")

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_SA)
    firebase_admin.initialize_app(cred)

db = firestore.client()

def create_scenario_metadata(scenario_id: str, payload: dict):
    db.collection("scenarios").document(scenario_id).set(payload)

def get_scenario_metadata(scenario_id: str):
    doc = db.collection("scenarios").document(scenario_id).get()
    return doc.to_dict() if doc.exists else None

def log_session_event(session_id: str, event: dict):
    db.collection("sessions").document(session_id).collection("events").add(event)
