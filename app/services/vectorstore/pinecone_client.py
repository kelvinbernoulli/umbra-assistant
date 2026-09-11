"""Pinecone vector storage client."""

from __future__ import annotations

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
    """Interface for vector storage operations."""

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


class PineconeClient:
    """Module-level accessor returning the Pinecone client, singleton per process."""

    _instance: VectorStoreClient | None = None
    _lock = threading.Lock()

    @classmethod
    def get_index(cls) -> VectorStoreClient:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    if not settings.PINECONE_API_KEY:
                        raise VectorStoreError("PINECONE_API_KEY is required for vector storage.")
                    cls._instance = RealPineconeClient()
        return cls._instance
