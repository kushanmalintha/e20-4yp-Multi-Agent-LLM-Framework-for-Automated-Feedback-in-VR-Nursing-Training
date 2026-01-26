import os
from openai import AsyncOpenAI
from app.core.config import OPENAI_API_KEY, VECTOR_STORE_ID

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not configured")

if not VECTOR_STORE_ID:
    raise RuntimeError("VECTOR_STORE_ID not configured")


class VectorClient:
    """
    Thin wrapper around OpenAI Vector Store file operations.

    - No embeddings
    - No chunking
    - No retrieval logic
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.vector_store_id = VECTOR_STORE_ID

    async def upload_file(self, scenario_id: str, file_path: str) -> str:
        """
        Upload a file to OpenAI Vector Store.

        NOTE:
        - scenario_id is NOT enforced by the API
        - scenario scoping is handled operationally during testing
        """

        with open(file_path, "rb") as f:
            uploaded_file = await self.client.files.create(
                file=f,
                purpose="assistants"
            )

        await self.client.vector_stores.files.create(
            vector_store_id=self.vector_store_id,
            file_id=uploaded_file.id
        )

        return uploaded_file.id

    async def delete_file(self, file_id: str):
        """
        Remove a file from the vector store.
        """
        await self.client.vector_stores.files.delete(
            vector_store_id=self.vector_store_id,
            file_id=file_id
        )
