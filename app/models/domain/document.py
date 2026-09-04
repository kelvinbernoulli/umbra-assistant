"""
Canonical internal representation of any piece of ingested content,
regardless of source. Every webhook normalizer must produce one (or more,
if chunked) of these before it reaches the embedding stage.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

SourceType = Literal["whatsapp", "gmail", "gcal", "manual"]
DocumentType = Literal["reminder", "summary", "message", "event"]


@dataclass
class Document:
    user_id: int
    text: str
    source: str | SourceType
    document_type: str | DocumentType

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    external_id: str | None = None  # provider-side message/event id, for idempotency
    thread_id: str | None = None  # conversation/thread grouping
    parent_id: str | None = None  # set when this Document is a chunk of a larger one
    created_at: int = field(default_factory=lambda: int(time.time()))
    raw_metadata: dict = field(
        default_factory=dict
    )  # provider-specific extras, not embedded

    def to_pinecone_metadata(self) -> dict:
        """Only fields safe/useful to store as Pinecone metadata — no raw secrets, no huge blobs."""
        meta = {
            "source": self.source,
            "document_type": self.document_type,
            "created_at": self.created_at,
            "text_preview": self.text[:280],
        }
        if self.thread_id:
            meta["thread_id"] = self.thread_id
        if self.parent_id:
            meta["parent_id"] = self.parent_id
        if self.external_id:
            meta["external_id"] = self.external_id
        return meta
