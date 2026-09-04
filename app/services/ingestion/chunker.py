"""
Document chunking service.

Splits large documents into overlapping chunks to ensure semantic coherence
during embedding. Uses token-based sizing (approx 1 token ≈ 4 chars) with
configurable chunk size and overlap percentage.

Example:
    doc = Document(user_id="123", text="Long text...", source="email", document_type="message")
    chunks = chunk_document(doc)  # Returns list of Documents with parent_id set
"""

from __future__ import annotations

import uuid
from typing import List

from app.models.domain.document import Document
from app.core.logging import get_logger

logger = get_logger(__name__)

# Rough heuristic: 1 token ≈ 4 characters on average
CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Rough estimate of token count based on character length."""
    return len(text) // CHARS_PER_TOKEN


def chunk_document(
    document: Document,
    chunk_size_tokens: int = 500,
    overlap_percent: float = 0.15,
) -> List[Document]:
    """
    Split a Document into overlapping chunks.

    Args:
        document: The Document to chunk
        chunk_size_tokens: Target size of each chunk in tokens (approx 400-600 recommended)
        overlap_percent: Overlap ratio between chunks (0.15 = 15%)

    Returns:
        List of Document chunks with parent_id pointing to original, or single Document
        if below chunk threshold.
    """
    text = document.text
    token_count = _estimate_tokens(text)

    # Short documents pass through unchanged
    if token_count <= chunk_size_tokens:
        return [document]

    # Calculate character stride from token size
    char_size = chunk_size_tokens * CHARS_PER_TOKEN
    overlap_chars = int(char_size * overlap_percent)
    stride = char_size - overlap_chars

    chunks: List[Document] = []
    for start_char in range(0, len(text), stride):
        end_char = min(start_char + char_size, len(text))
        chunk_text = text[start_char:end_char]

        # Skip tiny fragments at the end
        if _estimate_tokens(chunk_text) < 10:
            if chunks:  # Append to last chunk instead
                chunks[-1].text += " " + chunk_text
            continue

        chunk = Document(
            user_id=document.user_id,
            text=chunk_text,
            source=document.source,
            document_type=document.document_type,
            id=str(uuid.uuid4()),
            external_id=document.external_id,
            thread_id=document.thread_id,
            parent_id=document.id,  # Link back to original
            created_at=document.created_at,
            raw_metadata=document.raw_metadata.copy(),
        )
        chunks.append(chunk)

    logger.info(
        "Chunked document id=%s into %d chunks (tokens: %d, chunk_size: %d)",
        document.id, len(chunks), token_count, chunk_size_tokens,
    )
    return chunks
