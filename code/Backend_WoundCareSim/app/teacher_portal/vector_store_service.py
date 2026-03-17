import os
import tempfile

from fastapi import UploadFile

from app.rag.vector_client import VectorClient


ALLOWED_EXTENSION = ".txt"


async def upload_guideline_file(file: UploadFile) -> str:
    filename = file.filename or ""
    if not filename.lower().endswith(ALLOWED_EXTENSION):
        raise ValueError("Only .txt files are allowed")

    content = await file.read()
    if not content:
        raise ValueError("Uploaded file is empty")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ALLOWED_EXTENSION) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        client = VectorClient()
        return await client.upload_file("teacher_guidelines", temp_path)
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
