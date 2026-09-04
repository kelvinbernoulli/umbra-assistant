"""Provision an API key for a user in the configured database."""

from __future__ import annotations

import argparse
import secrets
from uuid import uuid4

from app.db.ingestion import provision_api_key
from app.db.session import SessionLocal


def create_api_key(user_id: str) -> tuple[str, str]:
    """Create and persist a random API key, returning its id and raw value once."""
    if not user_id.strip():
        raise ValueError("User ID cannot be empty")
    key_id = str(uuid4())
    raw_key = secrets.token_urlsafe(32)
    db = SessionLocal()
    try:
        provision_api_key(db, key_id=key_id, user_id=user_id.strip(), raw_key=raw_key)
    finally:
        db.close()
    return key_id, raw_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision an Umbra API key")
    parser.add_argument("user_id")
    args = parser.parse_args()
    key_id, raw_key = create_api_key(args.user_id)
    print(f"key_id={key_id}")
    print(f"api_key={raw_key}")
    print("Store the API key securely; it will not be shown again.")


if __name__ == "__main__":
    main()
