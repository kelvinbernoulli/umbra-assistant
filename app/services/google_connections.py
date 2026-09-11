"""Encrypted Google credentials, scoped to the authenticated Umbra user."""
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import Column, MetaData, String, Table, Text, create_engine, delete, inspect, select, update
from sqlalchemy.engine import make_url

from app.core.config import settings

metadata = MetaData()
credentials = Table(
    "oauth_credentials", metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(255), nullable=False, index=True),
    Column("provider", String(64), nullable=False),
    Column("encrypted_token", Text, nullable=False),
    Column("connected_at", String(40), nullable=False),
)


@lru_cache
def _engine(url: str):
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite" and parsed.database not in (None, "", ":memory:"):
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, pool_pre_ping=True)


def get_engine():
    return _engine(settings.CREDENTIAL_DB_URL or settings.DATABASE_URL)


def cipher():
    try:
        if not settings.CREDENTIAL_ENCRYPTION_KEY:
            raise ValueError("Missing encryption key")
        return Fernet(settings.CREDENTIAL_ENCRYPTION_KEY.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, "Google connection storage needs a valid CREDENTIAL_ENCRYPTION_KEY.") from None


def save_refresh_token(user_id: str, refresh_token: str):
    encrypted = cipher().encrypt(refresh_token.encode()).decode()
    engine = get_engine()
    metadata.create_all(engine)
    identity = sha256(f"{user_id}:gcal".encode()).hexdigest()
    values = dict(user_id=user_id, provider="gcal", encrypted_token=encrypted,
                  connected_at=datetime.now(timezone.utc).isoformat())
    with engine.begin() as connection:
        existing = connection.scalar(select(credentials.c.id).where(credentials.c.id == identity))
        if existing:
            connection.execute(update(credentials).where(credentials.c.id == identity).values(**values))
        else:
            connection.execute(credentials.insert().values(id=identity, **values))


def list_statuses(user_id: str):
    engine = get_engine()
    if not inspect(engine).has_table(credentials.name):
        return []
    with engine.connect() as connection:
        rows = connection.execute(select(credentials.c.id, credentials.c.provider, credentials.c.connected_at)
                                  .where(credentials.c.user_id == user_id)).mappings().all()
    return [dict(row, status="connected") for row in rows]


def disconnect(user_id: str, provider: str):
    engine = get_engine()
    if not inspect(engine).has_table(credentials.name):
        return
    with engine.begin() as connection:
        connection.execute(delete(credentials).where(credentials.c.user_id == user_id,
                                                      credentials.c.provider == provider))
