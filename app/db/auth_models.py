"""Database-backed Google identities and revocable browser sessions."""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models import Base


class GoogleUser(Base):
    __tablename__ = "google_users"
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    api_key_id: Mapped[str] = mapped_column(ForeignKey("api_keys.id"), nullable=False)


class BrowserSession(Base):
    __tablename__ = "browser_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("google_users.id"), nullable=False)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False, index=True)


class LoginChallenge(Base):
    __tablename__ = "login_challenges"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
