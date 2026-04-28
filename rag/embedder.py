"""
rag/embedder.py
---------------
Converts text chunks into vector embeddings using a lightweight
sentence-transformers model that runs locally (free, no API call needed).

Model: all-MiniLM-L6-v2 (~80MB) – fast and good quality for code.
"""
import logging
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Loaded once at module import and cached in memory
_MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazy-load the embedding model (cached singleton)."""
    global _model
    if _model is None:
        logger.info(f"[Embedder] Loading model: {_MODEL_NAME}")
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Embed a list of strings into a float32 numpy array of shape (N, dim).
    Uses batched inference for efficiency.
    """
    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,  # L2 normalise → cosine similarity = dot product
    )
    return embeddings.astype(np.float32)


def embed_single(text: str) -> np.ndarray:
    """Embed a single query string. Returns shape (dim,)."""
    return embed_texts([text])[0]
