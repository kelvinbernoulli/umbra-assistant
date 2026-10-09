"""Admin-only account analytics."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.auth_models import GoogleUser
from app.db.models import SourceItem, Workspace, WorkspaceIntegration
from app.db.session import get_db
from app.services.browser_session import session_user

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(request: Request, db: Session) -> GoogleUser:
    user = session_user(request, db)
    allowed_emails = {email.strip().casefold() for email in settings.ADMIN_EMAILS if email.strip()}
    if user.email.strip().casefold() not in allowed_emails:
        raise HTTPException(403, "Administrator access is required.")
    return user


def _workspace_stats():
    item_stats = (
        select(
            SourceItem.workspace_id.label("workspace_id"),
            func.count(SourceItem.id).label("stored_items"),
            func.max(SourceItem.created_at).label("last_data_at"),
        )
        .group_by(SourceItem.workspace_id)
        .subquery()
    )
    integration_stats = (
        select(
            WorkspaceIntegration.workspace_id.label("workspace_id"),
            func.count(func.distinct(WorkspaceIntegration.provider)).label("active_sources"),
        )
        .where(WorkspaceIntegration.active.is_(True))
        .group_by(WorkspaceIntegration.workspace_id)
        .subquery()
    )
    return item_stats, integration_stats


def _user_metrics(stored_items: int | None, last_data_at, active_sources: int | None) -> dict:
    return {
        "stored_items": stored_items or 0,
        "last_data_at": last_data_at,
        "active_sources": active_sources or 0,
    }


@router.get("/users")
def list_users(request: Request, response: Response, db: Session = Depends(get_db)):
    require_admin(request, db)
    response.headers["Cache-Control"] = "no-store"
    item_stats, integration_stats = _workspace_stats()
    rows = db.execute(
        select(
            GoogleUser,
            Workspace,
            item_stats.c.stored_items,
            item_stats.c.last_data_at,
            integration_stats.c.active_sources,
        )
        .outerjoin(Workspace, Workspace.id == GoogleUser.workspace_id)
        .outerjoin(item_stats, item_stats.c.workspace_id == GoogleUser.workspace_id)
        .outerjoin(integration_stats, integration_stats.c.workspace_id == GoogleUser.workspace_id)
        .order_by(GoogleUser.name, GoogleUser.email)
    ).all()
    return {
        "total": len(rows),
        "items": [
            {
                "user": {"id": user.id, "name": user.name, "email": user.email},
                "workspace": (
                    {"id": workspace.id, "name": workspace.name}
                    if workspace else {"id": user.workspace_id, "name": user.workspace_id}
                ),
                "metrics": _user_metrics(stored_items, last_data_at, active_sources),
            }
            for user, workspace, stored_items, last_data_at, active_sources in rows
        ],
    }


@router.get("/users/{user_id}")
def get_user(user_id: str, request: Request, response: Response, db: Session = Depends(get_db)):
    require_admin(request, db)
    response.headers["Cache-Control"] = "no-store"
    user = db.get(GoogleUser, user_id)
    if user is None:
        raise HTTPException(404, "User not found.")

    workspace = db.get(Workspace, user.workspace_id)
    item_stats, integration_stats = _workspace_stats()
    stored_items, last_data_at, active_sources = db.execute(
        select(item_stats.c.stored_items, item_stats.c.last_data_at, integration_stats.c.active_sources)
        .select_from(item_stats.outerjoin(
            integration_stats, integration_stats.c.workspace_id == item_stats.c.workspace_id
        ))
        .where(item_stats.c.workspace_id == user.workspace_id)
    ).one_or_none() or (None, None, None)
    source_rows = db.execute(
        select(SourceItem.source, func.count(SourceItem.id).label("count"))
        .where(SourceItem.workspace_id == user.workspace_id)
        .group_by(SourceItem.source)
        .order_by(func.count(SourceItem.id).desc(), SourceItem.source)
    ).all()
    if active_sources is None:
        active_sources = db.scalar(
            select(integration_stats.c.active_sources).where(
                integration_stats.c.workspace_id == user.workspace_id
            )
        )
    return {
        "user": {"id": user.id, "name": user.name, "email": user.email},
        "workspace": (
            {"id": workspace.id, "name": workspace.name}
            if workspace else {"id": user.workspace_id, "name": user.workspace_id}
        ),
        "metrics": _user_metrics(stored_items, last_data_at, active_sources),
        "sources": [{"name": source, "stored_items": count} for source, count in source_rows],
    }
