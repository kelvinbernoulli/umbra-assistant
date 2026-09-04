"""
Thin wrapper around the Pinecone SDK, plus an in-memory mock implementation
used automatically when PINECONE_API_KEY is not configured.

Both implementations expose the same minimal interface (upsert / query)
so the rest of the app never needs to know which one is active.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.exceptions import VectorStoreError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VectorMatch:
    id: str
    score: float
    metadata: dict


@dataclass
class QueryResult:
    matches: list[VectorMatch] = field(default_factory=list)


class VectorStoreClient:
    """Interface both the real and mock clients implement."""

    def upsert(self, namespace: str, vectors: list[tuple[str, list[float], dict]]) -> None:
        raise NotImplementedError

    def query(
        self,
        namespace: str,
        vector: list[float],
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
        include_metadata: bool = True,
    ) -> QueryResult:
        raise NotImplementedError

    def delete(self, namespace: str, ids: list[str]) -> None:
        raise NotImplementedError


class MockVectorStoreClient(VectorStoreClient):
    """
    In-memory, thread-safe, namespace-isolated vector store.
    Cosine similarity over Python lists — fine for dev/test volumes,
    not intended for production scale.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # namespace -> {id: (vector, metadata)}
        self._store: dict[str, dict[str, tuple[list[float], dict]]] = {}

    def upsert(self, namespace: str, vectors: list[tuple[str, list[float], dict]]) -> None:
        with self._lock:
            bucket = self._store.setdefault(namespace, {})
            for vec_id, vector, metadata in vectors:
                bucket[vec_id] = (vector, metadata)
        logger.debug("Mock upsert: ns=%s count=%d", namespace, len(vectors))

    def query(
        self,
        namespace: str,
        vector: list[float],
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
        include_metadata: bool = True,
    ) -> QueryResult:
        with self._lock:
            bucket = self._store.get(namespace, {})
            scored: list[VectorMatch] = []
            for vec_id, (stored_vec, metadata) in bucket.items():
                if not _matches_filter(metadata, filter):
                    continue
                score = _cosine_similarity(vector, stored_vec)
                scored.append(VectorMatch(id=vec_id, score=score, metadata=metadata))

        scored.sort(key=lambda m: m.score, reverse=True)
        return QueryResult(matches=scored[:top_k])

    def delete(self, namespace: str, ids: list[str]) -> None:
        with self._lock:
            bucket = self._store.get(namespace, {})
            for vec_id in ids:
                bucket.pop(vec_id, None)


class RealPineconeClient(VectorStoreClient):
    """Lazy-initialized wrapper around the actual Pinecone SDK."""

    def __init__(self) -> None:
        try:
            from pinecone import Pinecone
        except ImportError as exc:
            raise VectorStoreError(
                "pinecone package not installed but PINECONE_API_KEY is set. "
                "Run: pip install pinecone"
            ) from exc

        self._pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self._index = self._pc.Index(settings.PINECONE_INDEX_NAME)

    def upsert(self, namespace: str, vectors: list[tuple[str, list[float], dict]]) -> None:
        payload = [{"id": vid, "values": vec, "metadata": meta} for vid, vec, meta in vectors]
        self._index.upsert(vectors=payload, namespace=namespace)

    def query(
        self,
        namespace: str,
        vector: list[float],
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
        include_metadata: bool = True,
    ) -> QueryResult:
        result = self._index.query(
            namespace=namespace,
            vector=vector,
            top_k=top_k,
            filter=filter or None,
            include_metadata=include_metadata,
        )
        matches = [
            VectorMatch(id=m["id"], score=m["score"], metadata=m.get("metadata", {}))
            for m in result.get("matches", [])
        ]
        return QueryResult(matches=matches)

    def delete(self, namespace: str, ids: list[str]) -> None:
        self._index.delete(ids=ids, namespace=namespace)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _matches_filter(metadata: dict, filter: dict[str, Any] | None) -> bool:
    """Supports the small subset of Pinecone filter syntax this app uses: {"field": {"$eq": val}}."""
    if not filter:
        return True
    for field_name, condition in filter.items():
        if isinstance(condition, dict) and "$eq" in condition:
            if metadata.get(field_name) != condition["$eq"]:
                return False
        else:
            if metadata.get(field_name) != condition:
                return False
    return True


class PineconeClient:
    """Module-level accessor returning the active client (real or mock), singleton per process."""

    _instance: VectorStoreClient | None = None
    _lock = threading.Lock()

    @classmethod
    def get_index(cls) -> VectorStoreClient:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    if settings.use_mock_vectorstore:
                        logger.warning(
                            "PINECONE_API_KEY not set — using in-memory MockVectorStoreClient. "
                            "Data will NOT persist across restarts."
                        )
                        cls._instance = MockVectorStoreClient()
                    else:
                        cls._instance = RealPineconeClient()
        return cls._instance
