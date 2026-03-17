import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBED_MODEL")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL")

GROQ_API_BASE_URL = os.getenv("GROQ_API_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")
GROQ_TTS_MODEL = os.getenv("GROQ_TTS_MODEL", "canopylabs/orpheus-v1-english")
GROQ_TTS_VOICE = os.getenv("GROQ_TTS_VOICE", "austin")
