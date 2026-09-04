"""
Version 1 routes for the dynamic `source` and `document_type` registry.

Stores sources (whatsapp, gmail, gcal, manual) and document types (reminder, summary, message, event)
in a local SQLite database. Built-in types are protected from deletion. Custom types can be added
to extend the system without code changes.

API Endpoints:
  GET  /api/v1/types/sources       — list all sources
  POST /api/v1/types/sources       — add a new source
  GET  /api/v1/types/document-types — list all document types
  POST /api/v1/types/document-types — add a new document type
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger
from app.db.type_registry import (
    add_document_type,
    add_source,
    is_valid_document_type,
    is_valid_source,
    list_document_types,
    list_sources,
)

logger = get_logger(__name__)

DEFAULT_SOURCES = {"whatsapp", "gmail", "gcal", "manual"}
DEFAULT_DOCUMENT_TYPES = {"reminder", "summary", "message", "event"}

# ---- FastAPI Router ----
router = APIRouter()


class RegistryItem(BaseModel):
    """A single registered source or document type."""

    name: str
    is_default: bool
    created_at: int


class AddItemRequest(BaseModel):
    """Request to add a new source or document type."""

    name: str


# ---- Endpoints ----


@router.get("/sources", response_model=list[RegistryItem])
async def list_sources_endpoint() -> list[RegistryItem]:
    """List all registered sources."""
    sources = list_sources()
    return [_as_response(item, DEFAULT_SOURCES) for item in sources]


@router.post("/sources", status_code=201, response_model=RegistryItem)
async def add_source_endpoint(req: AddItemRequest) -> RegistryItem:
    """Add a new source to the registry."""
    if not req.name or not req.name.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid source name")
    if is_valid_source(req.name):
        raise HTTPException(status_code=409, detail=f"Source '{req.name}' already exists")
    add_source(req.name)
    return _as_response({"name": req.name}, DEFAULT_SOURCES)


@router.get("/document-types", response_model=list[RegistryItem])
async def list_document_types_endpoint() -> list[RegistryItem]:
    """List all registered document types."""
    doc_types = list_document_types()
    return [_as_response(item, DEFAULT_DOCUMENT_TYPES) for item in doc_types]


@router.post("/document-types", status_code=201, response_model=RegistryItem)
async def add_document_type_endpoint(req: AddItemRequest) -> RegistryItem:
    """Add a new document type to the registry."""
    if not req.name or not req.name.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid document type name")
    if is_valid_document_type(req.name):
        raise HTTPException(status_code=409, detail=f"Document type '{req.name}' already exists")
    add_document_type(req.name)
    return _as_response({"name": req.name}, DEFAULT_DOCUMENT_TYPES)


def _as_response(item: dict[str, object], defaults: set[str]) -> RegistryItem:
    name = str(item["name"])
    return RegistryItem(name=name, is_default=name in defaults, created_at=int(time.time()))


class RegistryError(Exception):
    """Raised when trying to remove a default type, or a type that doesn't exist."""


def remove_source(name: str) -> None:
    if name in DEFAULT_SOURCES:
        raise RegistryError(f"'{name}' is a default source and can't be removed")
    raise RegistryError("Removing custom registry entries is not supported yet")


def remove_document_type(name: str) -> None:
    if name in DEFAULT_DOCUMENT_TYPES:
        raise RegistryError(f"'{name}' is a default document type and can't be removed")
    raise RegistryError("Removing custom registry entries is not supported yet")
