import os
import base64
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dotenv import load_dotenv
load_dotenv()

from .rag import query_vector_store
from .groq_client import groq_stt_from_bytes, groq_tts_to_bytes
from .firebase_client import get_scenario_metadata, log_session_event
from .utils import gen_id

from openai import OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/ask")
async def api_ask(scenario_id: str = Form(...), text: str = Form(None), audio: UploadFile = File(None)):
    session_id = gen_id("sess")
    # 1) STT if audio provided
    transcript = None
    if audio is not None:
        audio_bytes = await audio.read()
        try:

            # Pass audio.filename so the function knows it is "file.mp3"
            transcript = groq_stt_from_bytes(audio_bytes, audio.filename)
            # ----------------------
        except Exception as e:
            # Added better logging for debugging
            print(f"STT ERROR: {e}") 
            return JSONResponse({"error": f"STT error: {str(e)}"}, status_code=500)

    else:
        transcript = text

    if not transcript:
        return JSONResponse({"error": "No transcript or text provided"}, status_code=400)

    # Log event
    try:
        log_session_event(session_id, {"event_type":"voice_transcript","payload":{"text":transcript}})
    except Exception:
        pass

    # 2) RAG retrieval
    context_snippets = ""
    try:
        retrieved = query_vector_store(query=transcript)
        context_snippets = "\n".join([r["text"] for r in retrieved if r.get("text")])
    except Exception as e:
        return JSONResponse({"error": f"Vector store error: {str(e)}"}, status_code=500)

    # 3) Scenario metadata
    scenario_meta = get_scenario_metadata(scenario_id) or {}
    meta_text = ""
    if scenario_meta:
        fields = []
        for k in ["title","patient_name","patient_age","diagnosis","short_description"]:
            if scenario_meta.get(k):
                fields.append(f"{k}: {scenario_meta.get(k)}")
        meta_text = " | ".join(fields)

    # 4) Build prompt and call OpenAI Chat
    messages = [
        {"role":"system","content":"You are a virtual patient. Answer briefly and consistently with the scenario metadata and retrieved context."},
    ]
    if meta_text:
        messages.append({"role":"system","content": f"Scenario metadata: {meta_text}"})
    if context_snippets:
        messages.append({"role":"system","content": f"Context:\n{context_snippets}"})
    messages.append({"role":"user","content": transcript})
    print("Messages to LLM:", messages)

    try:
        resp = client.chat.completions.create(model=CHAT_MODEL, messages=messages, max_tokens=250)
        reply_text = resp.choices[0].message.content
    except Exception as e:
        return JSONResponse({"error": f"LLM error: {str(e)}"}, status_code=500)

    # 5) TTS via Groq
    audio_b64 = None
    try:
        audio_bytes = groq_tts_to_bytes(reply_text)
        audio_b64 = base64.b64encode(audio_bytes).decode('ascii')
    except Exception as e:
        audio_b64 = None
        print(f"TTS error: {e}")  # Or log the error

    # Log agent response
    try:
        log_session_event(session_id, {"event_type":"agent_response","payload":{"text":reply_text}})
    except Exception:
        pass

    return {"text": reply_text, "audio_base64": audio_b64}
