import json
import os
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine, text

_REGISTRY_PATH = Path(__file__).resolve().parent / "type_registry.json"
_DEFAULT_SOURCES = {"gmail", "gcal", "whatsapp", "manual"}
_DEFAULT_DOCUMENT_TYPES = {"reminder", "summary", "message", "event"}

# If DATABASE_URL is set, prefer Postgres-backed storage.
_DATABASE_URL = os.environ.get("DATABASE_URL")
_ENGINE = None
if _DATABASE_URL:
    try:
        _ENGINE = create_engine(_DATABASE_URL, future=True)
        # ensure table exists
        with _ENGINE.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS type_registry (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        UNIQUE (name, kind)
                    )
                    """
                )
            )
    except Exception:
        _ENGINE = None


def _load_registry() -> tuple[set[str], set[str]]:
    if _ENGINE:
        with _ENGINE.connect() as conn:
            sources = {row[0] for row in conn.execute(text("SELECT name FROM type_registry WHERE kind='source'"))}
            document_types = {row[0] for row in conn.execute(text("SELECT name FROM type_registry WHERE kind='document_type'"))}
            if not sources:
                sources = set(_DEFAULT_SOURCES)
            if not document_types:
                document_types = set(_DEFAULT_DOCUMENT_TYPES)
            return sources, document_types

    # fallback to JSON file
    if not _REGISTRY_PATH.exists():
        return set(_DEFAULT_SOURCES), set(_DEFAULT_DOCUMENT_TYPES)

    try:
        data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set(_DEFAULT_SOURCES), set(_DEFAULT_DOCUMENT_TYPES)

    sources = {_canonical_source(name) for name in data.get("sources", [])}
    document_types = set(data.get("document_types", []))
    if not sources:
        sources = set(_DEFAULT_SOURCES)
    if not document_types:
        document_types = set(_DEFAULT_DOCUMENT_TYPES)
    return sources, document_types


def _canonical_source(name: str) -> str:
    normalized = name.strip().lower()
    return "gcal" if normalized == "google_calendar" else normalized


def _save_registry(sources: Iterable[str], document_types: Iterable[str]) -> None:
    # save to Postgres if available
    if _ENGINE:
        with _ENGINE.begin() as conn:
            # upsert provided sets
            for name in sources:
                conn.execute(
                    text(
                        "INSERT INTO type_registry (name, kind) VALUES (:name, 'source') ON CONFLICT (name, kind) DO NOTHING"
                    ),
                    {"name": name},
                )
            for name in document_types:
                conn.execute(
                    text(
                        "INSERT INTO type_registry (name, kind) VALUES (:name, 'document_type') ON CONFLICT (name, kind) DO NOTHING"
                    ),
                    {"name": name},
                )
        return

    _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sources": sorted(sources),
        "document_types": sorted(document_types),
    }
    _REGISTRY_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


_SOURCES, _DOCUMENT_TYPES = _load_registry()


def list_sources() -> list[dict[str, object]]:
    """Return the registered source names for the connections endpoint."""
    if _ENGINE:
        with _ENGINE.connect() as conn:
            rows = conn.execute(text("SELECT name FROM type_registry WHERE kind='source' ORDER BY name"))
            return [{"name": r[0]} for r in rows]
    return [{"name": name} for name in sorted(_SOURCES)]


def add_source(name: str) -> None:
    normalized = _canonical_source(name)
    if not normalized:
        return
    if _ENGINE:
        with _ENGINE.begin() as conn:
            conn.execute(text("INSERT INTO type_registry (name, kind) VALUES (:name, 'source') ON CONFLICT (name, kind) DO NOTHING"), {"name": normalized})
        return

    _SOURCES.add(normalized)
    _save_registry(_SOURCES, _DOCUMENT_TYPES)


def list_document_types() -> list[dict[str, object]]:
    """Return the registered document types for ingestion validation."""
    if _ENGINE:
        with _ENGINE.connect() as conn:
            rows = conn.execute(text("SELECT name FROM type_registry WHERE kind='document_type' ORDER BY name"))
            return [{"name": r[0]} for r in rows]
    return [{"name": name} for name in sorted(_DOCUMENT_TYPES)]


def add_document_type(name: str) -> None:
    normalized = name.strip().lower()
    if not normalized:
        return
    if _ENGINE:
        with _ENGINE.begin() as conn:
            conn.execute(text("INSERT INTO type_registry (name, kind) VALUES (:name, 'document_type') ON CONFLICT (name, kind) DO NOTHING"), {"name": normalized})
        return

    _DOCUMENT_TYPES.add(normalized)
    _save_registry(_SOURCES, _DOCUMENT_TYPES)


def is_valid_source(source: str) -> bool:
    source = _canonical_source(source)
    if _ENGINE:
        with _ENGINE.connect() as conn:
            rows = conn.execute(text("SELECT 1 FROM type_registry WHERE kind='source' AND name = :name"), {"name": source.lower()})
            return rows.first() is not None
    return source.lower() in _SOURCES


def is_valid_document_type(document_type: str) -> bool:
    if _ENGINE:
        with _ENGINE.connect() as conn:
            rows = conn.execute(text("SELECT 1 FROM type_registry WHERE kind='document_type' AND name = :name"), {"name": document_type.lower()})
            return rows.first() is not None
    return document_type.lower() in _DOCUMENT_TYPES
