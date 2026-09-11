"""Verify Google sign-in, provision an account atomically, and issue a session."""
import secrets
import time
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.auth_models import BrowserSession, GoogleUser, LoginChallenge
from app.db.models import ApiKey, Workspace, WorkspaceMember
from app.db.session import get_db
from app.services.browser_session import (
    CHALLENGE_COOKIE, SESSION_COOKIE, digest, require_browser_origin, session_user,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


class GoogleSignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential: str = Field(min_length=1, max_length=16384)


def private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def set_cookie(response: Response, name: str, token: str, lifetime: int) -> None:
    response.set_cookie(name, token, httponly=True, secure=settings.SESSION_COOKIE_SECURE,
                        samesite="lax", max_age=lifetime, path="/")


def public_user(user: GoogleUser) -> dict:
    return {"user": {"id": user.id, "email": user.email, "name": user.name},
            "workspace": {"id": user.workspace_id}}


@router.post("/challenge")
def challenge(request: Request, response: Response, db: Session = Depends(get_db)):
    require_browser_origin(request)
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google sign-in is not configured on the server.")
    now = int(time.time())
    previous = request.cookies.get(CHALLENGE_COOKIE)
    if previous:
        db.execute(delete(LoginChallenge).where(LoginChallenge.token_hash == digest(previous)))
    db.execute(delete(LoginChallenge).where(LoginChallenge.expires_at <= now))
    db.execute(delete(BrowserSession).where(BrowserSession.expires_at <= now))
    nonce = secrets.token_urlsafe(32)
    db.add(LoginChallenge(token_hash=digest(nonce), expires_at=now + 300))
    db.commit()
    set_cookie(response, CHALLENGE_COOKIE, nonce, 300)
    private_response(response)
    return {"nonce": nonce}


@router.post("/google")
def google_sign_in(payload: GoogleSignIn, request: Request, response: Response,
                   db: Session = Depends(get_db)):
    require_browser_origin(request)
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google sign-in is not configured on the server.")
    nonce = request.cookies.get(CHALLENGE_COOKIE)
    stored = db.get(LoginChallenge, digest(nonce)) if nonce else None
    if stored is None or stored.expires_at <= int(time.time()):
        raise HTTPException(401, "Sign-in expired. Please try again.")
    try:
        claims = id_token.verify_oauth2_token(payload.credential, GoogleRequest(), settings.GOOGLE_CLIENT_ID)
    except ValueError:
        raise HTTPException(401, "Google identity could not be verified.") from None
    except Exception:
        raise HTTPException(503, "Google verification is temporarily unavailable.") from None
    if (not isinstance(claims.get("sub"), str) or not claims["sub"]
            or len(claims["sub"]) > 255 or claims.get("email_verified") is not True
            or not isinstance(claims.get("email"), str) or not claims["email"]
            or len(claims["email"]) > 320
            or not isinstance(claims.get("nonce"), str)
            or not secrets.compare_digest(claims["nonce"], nonce)):
        raise HTTPException(401, "Google identity or sign-in challenge is invalid.")
    consumed = db.execute(delete(LoginChallenge).where(
        LoginChallenge.token_hash == digest(nonce), LoginChallenge.expires_at > int(time.time())
    ))
    if consumed.rowcount != 1:
        db.rollback()
        raise HTTPException(401, "Sign-in challenge was already used.")
    db.commit()
    user = db.scalar(select(GoogleUser).where(GoogleUser.google_sub == claims["sub"]))
    if user is None:
        user_id, workspace_id, key_id = str(uuid4()), str(uuid4()), str(uuid4())
        name = str(claims.get("name") or claims["email"])[:255]
        db.add(Workspace(id=workspace_id, name=f"{name[:200]}'s workspace"))
        # API keys remain server-side and are stored only as hashes.
        db.add(ApiKey(id=key_id, user_id=user_id, key_hash=digest(secrets.token_urlsafe(32)), active=True))
        db.flush()
        db.add(WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="owner"))
        user = GoogleUser(id=user_id, google_sub=claims["sub"], email=claims["email"],
                          name=name, workspace_id=workspace_id, api_key_id=key_id)
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            user = db.scalar(select(GoogleUser).where(GoogleUser.google_sub == claims["sub"]))
            if user is None:
                raise HTTPException(503, "Account creation failed. Please try again.") from None
    key = db.get(ApiKey, user.api_key_id)
    membership = db.get(WorkspaceMember, (user.workspace_id, user.id))
    if key is None or not key.active or membership is None:
        raise HTTPException(403, "Account access is disabled. Contact your administrator.")
    user.email = claims["email"]
    user.name = str(claims.get("name") or claims["email"])[:255]
    previous = request.cookies.get(SESSION_COOKIE)
    if previous:
        db.execute(delete(BrowserSession).where(BrowserSession.token_hash == digest(previous)))
    token = secrets.token_urlsafe(32)
    lifetime = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    db.add(BrowserSession(token_hash=digest(token), user_id=user.id, expires_at=int(time.time()) + lifetime))
    db.commit()
    set_cookie(response, SESSION_COOKIE, token, lifetime)
    response.delete_cookie(CHALLENGE_COOKIE, path="/", secure=settings.SESSION_COOKIE_SECURE, httponly=True, samesite="lax")
    private_response(response)
    return public_user(user)


@router.get("/session")
def current_session(request: Request, response: Response, db: Session = Depends(get_db)):
    user = session_user(request, db)
    private_response(response)
    return public_user(user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    require_browser_origin(request)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute(delete(BrowserSession).where(BrowserSession.token_hash == digest(token)))
    nonce = request.cookies.get(CHALLENGE_COOKIE)
    if nonce:
        db.execute(delete(LoginChallenge).where(LoginChallenge.token_hash == digest(nonce)))
    db.commit()
    for name in (SESSION_COOKIE, CHALLENGE_COOKIE):
        response.delete_cookie(name, path="/", secure=settings.SESSION_COOKIE_SECURE, httponly=True, samesite="lax")
    private_response(response)
