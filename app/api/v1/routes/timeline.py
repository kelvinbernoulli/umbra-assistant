"""Timeline HTTP routes."""

from fastapi import APIRouter
from app.models.schemas.timeline_event import TimelineEventResponse
from datetime import datetime
from typing import List

router = APIRouter(prefix="/timeline", tags=["Timeline"])

@router.get("", response_model=List[TimelineEventResponse])
async def get_timeline_events():
    return [
        TimelineEventResponse(id="event-1", source="email", type="message", timestamp=datetime.utcnow(), title="Sample event", detail="This is a timeline placeholder."),
    ]
