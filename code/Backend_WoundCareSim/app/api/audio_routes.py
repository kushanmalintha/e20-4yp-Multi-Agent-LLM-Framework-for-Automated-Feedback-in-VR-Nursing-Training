from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.groq_audio_service import GroqAudioService


router = APIRouter(prefix="/audio", tags=["Audio"])
audio_service = GroqAudioService()


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    model: Optional[str] = None


@router.post("/stt")
async def transcribe_audio(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = await audio_service.transcribe_audio(
            filename=file.filename or "audio.webm",
            content=content,
            content_type=file.content_type or "application/octet-stream",
        )
        return {"text": text}
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="STT request failed") from exc


@router.post("/tts")
async def text_to_speech(payload: TTSRequest):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text is required for TTS")
    try:
        audio = await audio_service.text_to_speech(
            text=payload.text,
            model=payload.model,
            voice=payload.voice,
        )
        return audio
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="TTS request failed") from exc
