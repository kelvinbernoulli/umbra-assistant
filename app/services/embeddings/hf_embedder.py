"""Hugging Face embedding service wrapper and deterministic development fake."""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)
_HASH_PERSONALIZATION = b"umbra-fake-v1"


class DeterministicFakeEmbedder:
    """Dependency-free embedding fake with stable lexical similarity.

    This is intentionally not a semantic model. It uses feature hashing over
    normalized words and adjacent word pairs so tests can make repeatable
    retrieval assertions without contacting an external model provider.
    """

    def __init__(self, embedding_dim: int):
        if embedding_dim <= 0:
            raise ValueError("embedding_dim must be greater than zero")
        self.embedding_dim = embedding_dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        canonical_text = unicodedata.normalize("NFKC", text).casefold()
        tokens = _TOKEN_PATTERN.findall(canonical_text)
        if not tokens:
            tokens = ["<empty>"]

        vector = [0.0] * self.embedding_dim

        for token in tokens:
            self._add_feature(vector, f"word:{token}", weight=1.0)

        for left, right in zip(tokens, tokens[1:]):
            self._add_feature(vector, f"pair:{left}\0{right}", weight=0.5)

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            # Distinct signed features can theoretically cancel in a very small
            # vector. A stable fallback keeps the Pinecone-compatible nonzero
            # vector guarantee intact.
            vector = [0.0] * self.embedding_dim
            self._add_feature(vector, f"fallback:{canonical_text}", weight=1.0)
            norm = 1.0

        return [value / norm for value in vector]

    def _add_feature(self, vector: list[float], feature: str, weight: float) -> None:
        digest = hashlib.blake2b(
            feature.encode("utf-8"),
            digest_size=8,
            person=_HASH_PERSONALIZATION,
        ).digest()
        bucket = int.from_bytes(digest[:4], byteorder="big") % self.embedding_dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign * weight


class HuggingFaceEmbedder:
    """Wrapper around the configured Hugging Face embedding model."""

    def __init__(self):
        self.model_name = settings.HUGGINGFACE_EMBEDDING_MODEL or "BAAI/bge-large-en-v1.5"
        self.embedding_dim = settings.HUGGINGFACE_EMBEDDING_DIM
        self._fake_embedder = DeterministicFakeEmbedder(self.embedding_dim)

        if settings.use_mock_embeddings:
            logger.info(
                "Using mock embeddings (no HF token configured): %s with dim=%d",
                self.model_name,
                self.embedding_dim,
            )
        else:
            logger.warning(
                "HF token configured, but real embeddings are not implemented; "
                "using deterministic fake: %s with dim=%d",
                self.model_name,
                self.embedding_dim,
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using the active implementation."""
        if settings.use_mock_embeddings:
            return self._fake_embedder.embed(texts)

        # TODO: Implement real HF Inference Endpoints call here.
        # Until then, keep development behavior stable rather than returning
        # misleading random vectors that can never be queried reproducibly.
        return self._fake_embedder.embed(texts)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Async wrapper for batch embedding."""
    embedder = HuggingFaceEmbedder()
    return embedder.embed(texts)
