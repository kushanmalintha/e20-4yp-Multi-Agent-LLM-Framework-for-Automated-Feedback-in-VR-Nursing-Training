from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.utils.firebase_client import get_firestore_client

router = APIRouter(prefix="/students", tags=["Students"])

@router.get("/{student_id}")
async def get_student(student_id: str) -> Dict[str, Any]:
    """Retrieve the top-level student document and their sessions_summary."""
    db = get_firestore_client()
    doc_ref = db.collection("students").document(student_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found.")
    return doc.to_dict()

@router.get("/{student_id}/sessions")
async def get_student_sessions(student_id: str) -> Dict[str, Any]:
    """
    Retrieve all sessions for a student. 
    By default, this relies on the lightweight sessions_summary array in the student doc
    so we don't have to fetch all full session documents.
    """
    db = get_firestore_client()
    doc_ref = db.collection("students").document(student_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found.")
        
    data = doc.to_dict()
    sessions = data.get("sessions_summary", [])
    
    return {
        "student_id": student_id,
        "sessions": sessions
    }

@router.get("/{student_id}/sessions/{session_id}")
async def get_session_detail(student_id: str, session_id: str) -> Dict[str, Any]:
    """Retrieve the full detailed log for a specific session."""
    db = get_firestore_client()
    doc_ref = db.collection("students").document(student_id).collection("sessions").document(session_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        # Check if student exists at all to provide a more accurate error
        student_doc = db.collection("students").document(student_id).get()
        if not student_doc.exists:
            raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found.")
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found for student '{student_id}'.")
        
    return doc.to_dict()
