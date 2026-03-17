import os
import requests

from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID")
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

def query_vector_store(query: str, filter: dict = None, top_k: int = 4):
    """
    Performs semantic query against the existing vector store.
    Returns list of {id, text, metadata, score}.
    """
    if not VECTOR_STORE_ID:
        raise RuntimeError("VECTOR_STORE_ID not set in env")
    url = f"https://api.openai.com/v1/vector_stores/{VECTOR_STORE_ID}/search"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": query,
            # "filter": filter or {}
    }
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("data", []):
        results.append({
            "id": item.get("id"),
            "text": item.get("text"),
            "metadata": item.get("metadata"),
            "score": item.get("score")
        })
    return results
