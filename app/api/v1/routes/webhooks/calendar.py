"""
Version 1 Google Calendar webhook receiver.

Google Calendar push notifications don't include the event payload
directly — they notify you that a channel changed, and you then call
the Calendar API to fetch what changed. This route models that as a
two-step: acknowledge the push notification, then (in a real
implementation) fetch the changed event(s) via the Calendar API inside
the background task before calling normalize_calendar_event. For now,
this route also accepts a direct event payload for local testing /
manual event ingestion, since standing up real GCal push channels is a
Phase 5 (OAuth) concern.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, Request
from pydantic import BaseModel

from app.core.logging import get_logger
from app.models.schemas.webhook_payloads import CalendarEventPayload
from app.services.ingestion.normalizer import normalize_calendar_event
from app.services.ingestion.pipeline import ingest_documents

logger = get_logger(__name__)
router = APIRouter()


class WebhookAckResponse(BaseModel):
    """Simple 202 Accepted response for webhook validation."""

    status: str = "accepted"
    message: str = "Webhook received"


async def _process_calendar_event(event_payload: dict[str, Any], user_id: str) -> None:
    """Normalize calendar event and queue for ingestion."""
    try:
        logger.info("Processing calendar event for user=%s", user_id)
        doc = normalize_calendar_event(event_payload, user_id)
        await ingest_documents([doc])
        logger.info("Successfully queued calendar event for ingestion")
    except Exception as exc:  # noqa: BLE001
        logger.error("Error processing calendar event: %s", exc, exc_info=True)


@router.post("/webhooks/gcal", status_code=202)
async def receive_calendar_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_goog_channel_id: str | None = Header(default=None),
    x_goog_resource_state: str | None = Header(default=None),
) -> WebhookAckResponse:
    """
    Receive and validate incoming calendar events.

    Google Calendar push notifications don't include event payloads directly,
    so this endpoint accepts direct event payloads for testing.

    In production (Phase 5), this would fetch changed events via the Calendar API.
    """
    if x_goog_channel_id:
        # Real Google push notification — no event body, just a "something changed" ping.
        logger.info(
            "GCal push notification: channel=%s state=%s — event fetching not yet implemented (Phase 5)",
            x_goog_channel_id,
            x_goog_resource_state,
        )
        return WebhookAckResponse(message="Push notification acknowledged (Phase 5 feature)")

    # Local/manual testing path: direct event payload.
    try:
        import json

        payload = json.loads(await request.body())
        event = CalendarEventPayload.model_validate(payload)
    except Exception as exc:
        logger.error("Failed to parse calendar event: %s", exc)
        raise ValueError(f"Invalid calendar event payload: {exc}") from exc

    # For testing, derive user_id from a header (in production, use auth context)
    user_id = "default-user"

    # Queue background task
    background_tasks.add_task(_process_calendar_event, payload, user_id)

    logger.info("Calendar event webhook received and queued: %s", event.summary)
    return WebhookAckResponse(message="Calendar event received and queued for processing")

    return IngestAck(accepted=True, document_ids=[doc.id])
