import math
import logging
from typing import List, Tuple, Optional
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import Mention
from src.config import settings

logger = logging.getLogger(__name__)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two float vectors (pure Python)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def embed_text(text: str, model: Optional[str] = None) -> Optional[List[float]]:
    """
    Generate embedding for text using Ollama.
    Returns float list or None if Ollama is unavailable.
    """
    target_model = model or settings.ollama.model
    host = settings.ollama.host.rstrip("/")

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{host}/api/embeddings",
                json={"model": target_model, "prompt": text[:2000]},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("embedding")
    except Exception as e:
        logger.debug(f"Could not generate embedding from Ollama: {e}")

    return None


def semantic_search(
    session: Session,
    query_embedding: List[float],
    limit: int = 10,
    min_similarity: float = 0.5,
) -> List[Tuple[Mention, float]]:
    """
    Perform semantic search using cosine similarity.
    """
    if not query_embedding:
        return []

    mentions = session.execute(
        select(Mention).where(Mention.embedding.is_not(None))
    ).scalars().all()

    results = []
    for mention in mentions:
        if mention.embedding is not None and isinstance(mention.embedding, list):
            sim = cosine_similarity(query_embedding, mention.embedding)
            if sim >= min_similarity:
                results.append((mention, sim))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


def keyword_search(
    session: Session,
    query: str,
    source: Optional[str] = None,
    limit: int = 20,
) -> List[Mention]:
    """Simple keyword search in title and content."""
    from .crud import get_mentions_by_keyword
    return get_mentions_by_keyword(session, query, source, limit)