"""
Orchestrates the full ingestion pipeline for a single normalized Document:

    normalize (caller's job) -> chunk -> embed -> upsert -> emit realtime event

This is the function background tasks call after a webhook has been
validated and its payload normalized into Document(s).
"""

from __future__ import annotations

from app.core.exceptions import IngestionError
from app.core.logging import get_logger
from app.db.type_registry import is_valid_document_type, is_valid_source
from app.models.domain.document import Document
from app.services.embeddings.hf_embedder import embed_batch
from app.services.ingestion.chunker import chunk_document
from app.services.realtime.event_bus import event_bus
from app.services.vectorstore.namespace_router import resolve_namespace
from app.services.vectorstore.pinecone_client import PineconeClient

logger = get_logger(__name__)


async def ingest_document(doc: Document) -> list[str]:
    """
    Runs one Document through chunk -> embed -> upsert -> emit.
    Returns the list of vector ids written to the store.
    """
    # Validate against the dynamic type registry BEFORE any embedding work —
    # this is the enforcement point that replaced the old Literal["whatsapp", ...]
    # type check. Reject fast and cheaply rather than silently accepting a
    # typo'd source/type that would otherwise be unfindable by filters later.
    if not is_valid_source(doc.source):
        raise IngestionError(
            f"Unknown source '{doc.source}' — register it first via "
            f"POST /api/v1/types/sources, or check for a typo."
        )
    if not is_valid_document_type(doc.document_type):
        raise IngestionError(
            f"Unknown document_type '{doc.document_type}' — register it first via "
            f"POST /api/v1/types/document-types, or check for a typo."
        )

    try:
        namespace = resolve_namespace(doc.user_id)
    except ValueError as exc:
        raise IngestionError(str(exc)) from exc

    chunks = chunk_document(doc)
    logger.info(
        "Ingesting document id=%s user=%s source=%s chunks=%d",
        doc.id, doc.user_id, doc.source, len(chunks),
    )

    try:
        vectors = await embed_batch([c.text for c in chunks])
    except Exception as exc:  # noqa: BLE001 - convert any embedding failure to a domain error
        raise IngestionError(f"Embedding failed for document {doc.id}: {exc}") from exc

    upsert_payload = [
        (chunk.id, vector, chunk.to_pinecone_metadata())
        for chunk, vector in zip(chunks, vectors)
    ]

    try:
        vector_store = PineconeClient.get_index()
        vector_store.upsert(namespace=namespace, vectors=upsert_payload)
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(f"Vector store upsert failed for document {doc.id}: {exc}") from exc

    # Emit ONE timeline event for the parent document (not per-chunk) —
    # the UI shows one card per logical message/email/event, not per chunk.
    await event_bus.publish(
        user_id=doc.user_id,
        event={
            "id": doc.id,
            "source": doc.source,
            "document_type": doc.document_type,
            "preview": doc.text[:280],
            "created_at": doc.created_at,
            "thread_id": doc.thread_id,
        },
    )

    return [c.id for c in chunks]


async def ingest_documents(docs: list[Document]) -> list[str]:
    """Convenience wrapper for batches (e.g. a WhatsApp webhook with multiple messages)."""
    all_ids: list[str] = []
    for doc in docs:
        ids = await ingest_document(doc)
        all_ids.extend(ids)
    return all_ids