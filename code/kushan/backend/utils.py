import uuid

def chunk_text(text: str, max_tokens: int = 200, overlap: int = 40):
    """
    Naive chunk by words (sufficient for week1).
    """
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i+max_tokens]
        chunks.append(" ".join(chunk_words))
        i += max_tokens - overlap
    return chunks

def gen_id(prefix="id"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"
