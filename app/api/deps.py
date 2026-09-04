from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.ingestion import is_workspace_member
from app.db.session import get_db


async def get_api_key(
    x_api_key: str | None = Header(None),
    db: Session = Depends(get_db),
) -> str:
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key header"
        )
    from app.db.ingestion import resolve_api_key_user

    user_id = resolve_api_key_user(db, raw_key=x_api_key)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return user_id


async def get_current_user_id(x_api_key: str = Depends(get_api_key)) -> str:
    """Placeholder dependency for authenticated requests.

    The current app uses this in the connections endpoints while auth is still being
    implemented. It returns the API key as a stand-in user identifier so the route
    layer can be exercised without introducing a full auth provider.
    """
    return x_api_key


async def get_current_workspace_id(
    x_workspace_id: str | None = Header(None),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing workspace header")
    workspace_id = x_workspace_id.strip()
    if not is_workspace_member(db, workspace_id=workspace_id, user_id=user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace access denied")
    return workspace_id
