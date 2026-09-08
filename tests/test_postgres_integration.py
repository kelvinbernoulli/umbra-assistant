"""Opt-in PostgreSQL integration checks.

Reads POSTGRES_DATABASE_URL from .env; if configured, tests run against it.
Otherwise tests skip cleanly.
"""

from __future__ import annotations

import os
import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Base, WebhookReceipt, Workspace


@pytest.fixture(scope="module")
def postgres_engine():
    load_dotenv()
    database_url = os.getenv("POSTGRES_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_DATABASE_URL is not set in .env")
    if not database_url.startswith("postgresql"):
        pytest.fail("POSTGRES_DATABASE_URL must use a PostgreSQL SQLAlchemy URL")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        Base.metadata.create_all(engine)
    except Exception as exc:
        engine.dispose()
        pytest.fail(f"PostgreSQL integration database is unavailable: {exc}")

    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.mark.postgres
def test_postgres_enforces_workspace_webhook_receipt_uniqueness(postgres_engine):
    with Session(postgres_engine) as db:
        db.add(Workspace(id="postgres-workspace", name="Postgres Workspace"))
        db.commit()
        db.add(
            WebhookReceipt(
                id="receipt-one",
                workspace_id="postgres-workspace",
                provider="gmail",
                external_id="message-one",
            )
        )
        db.commit()
        db.add(
            WebhookReceipt(
                id="receipt-two",
                workspace_id="postgres-workspace",
                provider="gmail",
                external_id="message-one",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()