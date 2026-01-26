import logging
from openai import AsyncOpenAI
from app.core.config import (
    OPENAI_API_KEY,
    VECTOR_STORE_ID,
    OPENAI_CHAT_MODEL,
)

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not configured")

if not VECTOR_STORE_ID:
    raise RuntimeError("VECTOR_STORE_ID not configured")

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def retrieve_with_rag(
    query: str,
    scenario_id: str,
    system_instruction: str = "You are a nursing guideline retrieval assistant."
):
    """
    Perform RAG using OpenAI Responses API + managed Vector Store.

    - Stateless
    - File-first
    - No manual chunking
    - No top_k
    """

    try:
        response = await client.responses.create(
            model=OPENAI_CHAT_MODEL,
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [VECTOR_STORE_ID]
                }
            ],
            input=[
                {
                    "role": "system",
                    "content": (
                        f"{system_instruction}\n"
                        f"CONSTRAINT: Use only information relevant to scenario_id={scenario_id}.\n"
                        f"Do NOT invent facts. If information is missing, say so."
                    )
                },
                {
                    "role": "user",
                    "content": query
                }
            ]
        )

        # -----------------------------
        # SAFE OUTPUT EXTRACTION
        # -----------------------------
        rag_text = ""

        if hasattr(response, "output"):
            for item in response.output:
                if getattr(item, "type", None) == "message":
                    for part in getattr(item, "content", []):
                        if getattr(part, "type", "") in ["text", "output_text"]:
                            rag_text += getattr(part, "text", "")

        rag_text = rag_text.strip()

        if not rag_text:
            logger.warning("RAG returned empty context")

        return {
            "text": rag_text,
            "raw_response": response
        }

    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        return {
            "text": "",
            "raw_response": None
        }
