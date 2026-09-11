import sqlite3
from pathlib import Path

from app.core.security import Security


def _default_db_path() -> Path:
    return Path("./data/credentials.db")


class CredentialStore:
    def __init__(self, db_path: str | Path, secret_key: str):
        self.db_path = Path(db_path)
        self.secret = Security(secret_key)
        self._ensure_db()

    def _ensure_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS credentials (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    encrypted_token TEXT NOT NULL
                )
                """
            )
        conn.close()

    def save(self, id: str, provider: str, token: str) -> None:
        encrypted = self.secret.encrypt(token)
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO credentials (id, provider, encrypted_token) VALUES (?, ?, ?)",
                (id, provider, encrypted)
            )
        conn.close()

    def get(self, id: str) -> str | None:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT encrypted_token FROM credentials WHERE id = ?",
            (id,)
        ).fetchone()
        conn.close()
        return self.secret.decrypt(row[0]) if row else None


def list_connection_statuses(user_id: str) -> list[dict[str, object]]:
    from app.services.google_connections import list_statuses
    return list_statuses(user_id)


def revoke_credential(user_id: str, provider: str) -> None:
    from app.services.google_connections import disconnect
    disconnect(user_id, provider)
