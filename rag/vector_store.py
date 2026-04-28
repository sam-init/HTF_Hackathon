"""
rag/vector_store.py
-------------------
FAISS-backed vector store for code chunks and documentation.

Each item stored has:
  - embedding vector (float32, 384-dim for MiniLM-L6-v2)
  - metadata dict: {"id", "text", "file", "type", "repo"}

Persistence: saves/loads from disk as .faiss + .json sidecar.
"""
import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import faiss
from rag.embedder import embed_texts, embed_single

logger = logging.getLogger(__name__)

STORE_DIR = Path("./data/vector_stores")
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dim


class FAISSVectorStore:
    """
    Wraps a FAISS IndexFlatIP (inner product, works as cosine sim
    when embeddings are L2-normalised) with a JSON metadata sidecar.
    """

    def __init__(self, store_name: str):
        """
        Args:
            store_name: logical name (e.g., "repo_owner_repo_name")
        """
        self.store_name = store_name
        self.index_path = STORE_DIR / f"{store_name}.faiss"
        self.meta_path = STORE_DIR / f"{store_name}.json"

        STORE_DIR.mkdir(parents=True, exist_ok=True)

        # Load from disk if exists, otherwise create new
        if self.index_path.exists() and self.meta_path.exists():
            self._load()
        else:
            self.index = faiss.IndexFlatIP(EMBEDDING_DIM)
            self.metadata: List[Dict[str, Any]] = []
            logger.info(f"[VectorStore] Created new store: {store_name}")

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]]) -> None:
        """
        Embed and insert a batch of texts with associated metadata.
        texts and metadatas must have the same length.
        """
        if not texts:
            return
        embeddings = embed_texts(texts)
        self.index.add(embeddings)
        for i, meta in enumerate(metadatas):
            meta["text"] = texts[i]
            self.metadata.append(meta)
        self._save()
        logger.info(f"[VectorStore] Added {len(texts)} items → total {self.index.ntotal}")

    def clear(self) -> None:
        """Remove all vectors from the store."""
        self.index.reset()
        self.metadata = []
        self._save()

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_fn: Optional[callable] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find the top-k most similar chunks to query.

        Args:
            query: natural language or code query
            k: number of results to return
            filter_fn: optional callable(meta) -> bool to post-filter results

        Returns:
            List of metadata dicts (with "text", "score" added)
        """
        if self.index.ntotal == 0:
            return []

        query_vec = embed_single(query).reshape(1, -1)
        actual_k = min(k * 3, self.index.ntotal)  # fetch 3× to allow filtering
        scores, indices = self.index.search(query_vec, actual_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            meta = dict(self.metadata[idx])
            meta["score"] = float(score)

            if filter_fn and not filter_fn(meta):
                continue
            results.append(meta)
            if len(results) >= k:
                break

        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        faiss.write_index(self.index, str(self.index_path))
        with open(self.meta_path, "w") as f:
            json.dump(self.metadata, f, indent=2)

    def _load(self) -> None:
        self.index = faiss.read_index(str(self.index_path))
        with open(self.meta_path) as f:
            self.metadata = json.load(f)
        logger.info(f"[VectorStore] Loaded store '{self.store_name}' ({self.index.ntotal} vectors)")
