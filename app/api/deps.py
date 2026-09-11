from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.ingestion import is_workspace_member, resolve_api_key_user
from app.db.session import get_db
from app.services.browser_session import SESSION_COOKIE, session_user


async def get_api_key(request: Request, x_api_key: str | None = Header(None), db: Session = Depends(get_db)) -> str:
    if request.cookies.get(SESSION_COOKIE):
        return session_user(request, db).id
    user_id = resolve_api_key_user(db, raw_key=x_api_key) if x_api_key else None
    if user_id is None:
        raise HTTPException(401, "Please sign in or supply a valid API key.")
    return user_id


async def get_current_user_id(user_id: str = Depends(get_api_key)) -> str:
    return user_id


async def get_current_workspace_id(request: Request, x_workspace_id: str | None = Header(None),
                                   user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)) -> str:
    if request.cookies.get(SESSION_COOKIE):
        workspace_id = session_user(request, db).workspace_id
    elif x_workspace_id and x_workspace_id.strip():
        workspace_id = x_workspace_id.strip()
    else:
        raise HTTPException(400, "Missing workspace header")
    if not is_workspace_member(db, workspace_id=workspace_id, user_id=user_id):
        raise HTTPException(403, "Workspace access denied")
    return workspace_id
