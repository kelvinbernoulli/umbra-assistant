"""Hugging Face semantic embeddings without synthetic fallbacks."""

from langchain_huggingface import HuggingFaceEmbeddings
from app.core.config import settings


class HuggingFaceEmbedder:
    """Wrapper around the configured Hugging Face embedding model."""

    def __init__(self):
        self.model_name = settings.HUGGINGFACE_EMBEDDING_MODEL or "BAAI/bge-large-en-v1.5"
        self.embedding_dim = settings.HUGGINGFACE_EMBEDDING_DIM
        self._real_embedder = HuggingFaceEmbeddings(
            model_name=self.model_name,
            encode_kwargs={"normalize_embeddings": True},
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return real model embeddings, propagating failures to the caller."""
        return self._real_embedder.embed_documents(texts)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Async wrapper for batch embedding."""
    embedder = HuggingFaceEmbedder()
    return embedder.embed(texts)
