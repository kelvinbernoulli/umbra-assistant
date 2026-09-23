"""Exercise database registry initialization without accessing configured databases."""
import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, text


def load_registry(monkeypatch, database_url):
    monkeypatch.setenv("DATABASE_URL", database_url)
    path = Path(__file__).resolve().parents[1] / "app/db/type_registry.py"
    spec = importlib.util.spec_from_file_location("isolated_type_registry", path)
    registry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(registry)
    assert registry._ENGINE is not None
    return registry


def test_fresh_database_lists_and_validates_builtins(tmp_path, monkeypatch):
    registry = load_registry(monkeypatch, f"sqlite:///{tmp_path / 'registry.db'}")
    try:
        assert {item["name"] for item in registry.list_sources()} == {
            "gmail", "gcal", "whatsapp", "manual",
        }
        assert {item["name"] for item in registry.list_document_types()} == {
            "reminder", "summary", "message", "event",
        }
        assert registry.is_valid_source("google_calendar")
        assert registry.is_valid_document_type("message")
        assert not registry.is_valid_source("unknown")
    finally:
        registry._ENGINE.dispose()


def test_existing_empty_table_is_repaired(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'registry.db'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE type_registry (name TEXT, kind TEXT, UNIQUE (name, kind))"
        ))
    engine.dispose()
    registry = load_registry(monkeypatch, url)
    try:
        assert len(registry.list_sources()) == 4
        assert len(registry.list_document_types()) == 4
    finally:
        registry._ENGINE.dispose()


def test_restart_preserves_custom_entries_without_duplicates(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'registry.db'}"
    registry = load_registry(monkeypatch, url)
    registry.add_source("custom")
    registry.add_document_type("note")
    registry._ENGINE.dispose()
    registry = load_registry(monkeypatch, url)
    try:
        assert len(registry.list_sources()) == 5
        assert len(registry.list_document_types()) == 5
        assert registry.is_valid_source("custom")
        assert registry.is_valid_document_type("note")
    finally:
        registry._ENGINE.dispose()
