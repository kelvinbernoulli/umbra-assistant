"""Daily overview with optional model synthesis and a factual fallback."""
from datetime import datetime, time, timedelta, timezone as utc_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_current_workspace_id
from app.db.models import SourceItem
from app.core.config import settings
from app.core.exceptions import UmbraError
from app.db.session import get_db
from app.models.schemas.brief import BriefResponse
from app.services.google_calendar import calendar_request
from app.services.llm.prompt_templates import BRIEF_SYSTEM_PROMPT, PromptTemplates
from app.services.llm.synthesis_llm import SynthesisLLM

router = APIRouter(prefix="/brief", tags=["Brief"])


@router.get("/today", response_model=BriefResponse)
def get_today_brief(
    timezone: str = Query("UTC", max_length=100),
    user_id: str = Depends(get_current_user_id),
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Use a valid IANA timezone, such as Africa/Lagos.") from None
    today = datetime.now(utc_timezone.utc).astimezone(zone).date()
    start = datetime.combine(today, time.min, tzinfo=zone)
    end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=zone)
    # Scope before limiting: never summarize another workspace's records.
    items = db.scalars(select(SourceItem).where(SourceItem.workspace_id == workspace_id)
                       .order_by(SourceItem.created_at.desc()).limit(100)).all()
    messages = sum(item.document_type in {"message", "email"} for item in items)
    reminders = sum(item.document_type == "reminder" for item in items)
    brief = BriefResponse(title="Daily overview", summary="")
    parts = []
    events = []
    try:
        result = calendar_request(user_id, "GET", params={
            "timeMin": start.isoformat(), "timeMax": end.isoformat(),
            "singleEvents": "true", "orderBy": "startTime", "maxResults": 250,
        })
        events = [event for event in result.get("items", []) if event.get("status") != "cancelled"]
        brief.calendar_count = len(events)
        brief.calendar_has_more = bool(result.get("nextPageToken"))
        brief.calendar_events = events[:3]
        if events:
            count = ("at least " if brief.calendar_has_more else "") + str(len(events))
            parts.append(f"You have {count} event{'s' if len(events) != 1 else ''} on your primary calendar today.")
            titles = [event.get("summary") or "Untitled event" for event in events[:3]]
            parts.append("On your schedule: " + "; ".join(titles) + ".")
        else:
            parts.append("No events on your primary calendar today.")
    except HTTPException as exc:
        # Keep saved activity usable if Google is disconnected, revoked or unavailable.
        if exc.status_code not in {400, 403, 404, 409, 429, 502, 503}:
            raise
        brief.calendar_notice = str(exc.detail)
        parts.append("Your calendar could not be loaded. " + brief.calendar_notice)
    except SQLAlchemyError:
        brief.calendar_notice = "Calendar connection storage is unavailable. Please try again later."
        parts.append(brief.calendar_notice)
    if items:
        parts.append(f"Your latest {len(items)} saved records include {messages} messages or emails and {reminders} reminders.")
    else:
        parts.append("You have no saved activity yet.")
    brief.summary = " ".join(parts)
    if settings.BRIEF_AI_ENABLED and (events or items):
        llm = SynthesisLLM()
        if not llm.configured:
            brief.summary_notice = "AI summaries are not enabled yet. Showing your daily overview."
        else:
            prompt = PromptTemplates.morning_brief_context(
                events, items=items, today=today.isoformat(), timezone=timezone,
                calendar_count=brief.calendar_count, calendar_has_more=brief.calendar_has_more,
                calendar_available=brief.calendar_notice is None,
            )
            try:
                brief.summary = llm.generate(prompt, system_prompt=BRIEF_SYSTEM_PROMPT)
                brief.summary_source = "ai"
                brief.title = "AI daily brief"
            except UmbraError:
                brief.summary_notice = "AI summary unavailable. Showing your daily overview instead."
    return brief
