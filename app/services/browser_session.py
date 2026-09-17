"""Shared session validation, with origin checks for browser mutations."""
import hashlib
import time
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.auth_models import BrowserSession, GoogleUser
from app.db.models import ApiKey
from app.db.ingestion import is_workspace_member

SESSION_COOKIE = "umbra_session"
CHALLENGE_COOKIE = "umbra_login_challenge"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def require_browser_origin(request: Request) -> None:
    if (request.headers.get("origin") not in settings.FRONTEND_ORIGINS
            or request.headers.get("x-requested-with") != "XMLHttpRequest"):
        raise HTTPException(403, "Invalid browser request origin.")


def session_user(request: Request, db: Session) -> GoogleUser:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise HTTPException(401, "Please sign in to Umbra.")
    session = db.get(BrowserSession, digest(raw))
    if session is None or session.expires_at <= int(time.time()):
        raise HTTPException(401, "Please sign in to Umbra.")
    user = db.get(GoogleUser, session.user_id)
    key = db.get(ApiKey, user.api_key_id) if user else None
    if user is None or key is None or not key.active or not is_workspace_member(
        db, workspace_id=user.workspace_id, user_id=user.id
    ):
        raise HTTPException(401, "Your session is no longer valid. Please sign in again.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_browser_origin(request)
    return user