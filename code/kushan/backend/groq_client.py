import os
import requests

# Ensure these are set in your environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_STT_URL = os.getenv("GROQ_STT_URL") 
GROQ_TTS_URL = os.getenv("GROQ_TTS_URL") 

def get_auth_headers():
    return {
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }

# -------------------------------------------
#  🔊 SPEECH → TEXT (STT) using Whisper v3
# -------------------------------------------
# In groq_client.py

def groq_stt_from_bytes(audio_bytes: bytes, filename: str) -> str:
    """
    Groq Whisper STT
    accepts filename to ensure correct extension (.mp3, .wav, etc) is sent to API
    """
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }
    
    # We use the actual filename (e.g., "upload.mp3") so requests can set the correct Content-Type automatically
    files = {
        "file": (filename, audio_bytes) 
    }
    
    data = {
        "model": "whisper-large-v3",
        "response_format": "json"
    }

    resp = requests.post(
        GROQ_STT_URL,
        headers=headers,
        files=files,
        data=data,
        timeout=60
    )
    
    if resp.status_code != 200:
        print(f"STT Error: {resp.text}")
        
    resp.raise_for_status()
    return resp.json().get("text", "")


# -------------------------------------------
#  🗣️ TEXT → SPEECH (TTS) using PlayAI
# -------------------------------------------
def groq_tts_to_bytes(text: str, voice: str = "Fritz-PlayAI", fmt: str = "mp3") -> bytes:
    """
    PlayAI TTS via Groq
    Model: playai-tts
    Common Voices: 
      - Fritz-PlayAI
      - Arista-PlayAI
      - Atlas-PlayAI
      - Magdalena-PlayAI
    """
    payload = {
        "model": "playai-tts",       # <-- CORRECTED: Model ID
        "input": text,
        "voice": voice,              # <-- Must be a PlayAI voice ID, not 'alloy'
        "response_format": fmt       # <-- CORRECTED: 'format' -> 'response_format'
    }

    # For JSON payload, we DO need Content-Type: application/json
    headers = get_auth_headers()
    headers["Content-Type"] = "application/json"

    resp = requests.post(
        GROQ_TTS_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    if resp.status_code != 200:
        print(f"TTS Error: {resp.text}")

    resp.raise_for_status()
    return resp.content

# -------------------------------------------
# Example Usage
# -------------------------------------------
if __name__ == "__main__":
    # Test TTS
    try:
        print("Generating Audio...")
        audio_data = groq_tts_to_bytes("Hello, this is a test of Play AI on Groq.")
        
        output_file = "output.mp3"
        with open(output_file, "wb") as f:
            f.write(audio_data)
        print(f"Audio saved to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")