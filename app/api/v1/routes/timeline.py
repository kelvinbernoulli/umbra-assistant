"""Workspace-scoped timeline HTTP routes."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace_id
from app.db.models import SourceItem
from app.db.session import get_db
from app.models.schemas.timeline_event import TimelineEventResponse

router = APIRouter(prefix="/timeline", tags=["Timeline"])


@router.get("", response_model=list[TimelineEventResponse])
async def get_timeline_events(
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[TimelineEventResponse]:
    items = db.scalars(
        select(SourceItem)
        .where(SourceItem.workspace_id == workspace_id)
        .order_by(SourceItem.created_at.desc())
        .limit(limit)
    ).all()

    events: list[TimelineEventResponse] = []
    for item in items:
        metadata = json.loads(item.payload_json or "{}")
        events.append(
            TimelineEventResponse(
                id=item.id,
                source=item.source,
                type=item.document_type,
                timestamp=item.created_at,
                title=metadata.get("email_subject") or item.document_type,
                detail=item.text,
            )
        )
    return events
