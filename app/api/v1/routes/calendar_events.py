"""List, create and edit the authenticated user's Google Calendar events."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime

from app.api.deps import get_current_user_id
from app.models.schemas.calendar import EventChanges, EventCreate
from app.services.google_calendar import calendar_request

router = APIRouter(prefix="/calendar/events", tags=["Calendar"])


@router.get("")
def list_events(calendar_id: str = Query("primary", min_length=1),
                time_min: AwareDatetime | None = None, time_max: AwareDatetime | None = None,
                page_token: str | None = None, limit: int = Query(50, ge=1, le=250),
                user_id: str = Depends(get_current_user_id)):
    start = time_min or datetime.now(timezone.utc)
    if time_max is not None and time_max <= start:
        raise HTTPException(422, "time_max must be after time_min")
    params = {"timeMin": start.isoformat(), "singleEvents": "true", "orderBy": "startTime", "maxResults": limit}
    if time_max is not None:
        params["timeMax"] = time_max.isoformat()
    if page_token:
        params["pageToken"] = page_token
    return calendar_request(user_id, "GET", calendar_id, params=params)


@router.post("", status_code=201)
def create_event(payload: EventCreate, calendar_id: str = Query("primary", min_length=1),
                 send_updates: Literal["all", "externalOnly", "none"] = "none",
                 user_id: str = Depends(get_current_user_id)):
    return calendar_request(user_id, "POST", calendar_id,
                            body=payload.model_dump(mode="json", exclude_none=True),
                            params={"sendUpdates": send_updates})


@router.patch("/{event_id}")
def update_event(event_id: str, payload: EventChanges,
                 calendar_id: str = Query("primary", min_length=1),
                 send_updates: Literal["all", "externalOnly", "none"] = "none",
                 user_id: str = Depends(get_current_user_id)):
    return calendar_request(user_id, "PATCH", calendar_id, event_id,
                            body=payload.model_dump(mode="json", exclude_unset=True, exclude_none=True),
                            params={"sendUpdates": send_updates})
