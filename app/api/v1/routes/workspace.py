from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.ingestion import (
    add_workspace_member,
    get_workspace_member_role,
    provision_workspace_webhook_token,
)
from app.db.models import Workspace
from app.db.session import get_db

router = APIRouter()


class WebhookTokenResponse(BaseModel):
    workspace_id: str
    token: str


@router.post(
    "/workspaces/{workspace_id}/webhook-token",
    response_model=WebhookTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def provision_webhook_token(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> WebhookTokenResponse:
    workspace = db.get(Workspace, workspace_id)
    role = get_workspace_member_role(db, workspace_id=workspace_id, user_id=user_id)
    if workspace is not None and role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace administration denied")

    if workspace is None:
        db.add(Workspace(id=workspace_id, name=workspace_id))
        db.commit()
        add_workspace_member(db, workspace_id=workspace_id, user_id=user_id, role="owner")

    token = secrets.token_urlsafe(32)
    provision_workspace_webhook_token(db, workspace_id=workspace_id, token=token)
    return WebhookTokenResponse(workspace_id=workspace_id, token=token)