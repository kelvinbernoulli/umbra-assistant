"""
Normalizers convert provider-specific payloads into canonical Document objects.

Each normalizer extracts relevant fields, maps them to the Document schema,
and preserves provider-specific metadata for later reference.

Normalizers are responsible for:
  1. Extracting text content
  2. Mapping source and document_type
  3. Extracting provider-specific IDs and metadata
  4. Determining user_id from context (passed as parameter)
  5. Handling timestamps
"""

from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger
from app.models.domain.document import Document

logger = get_logger(__name__)


def normalize_whatsapp_message(
    payload: dict[str, Any], user_id: str
) -> Document:
    """
    Normalize a WhatsApp message from Meta Webhook API.

    Expected payload structure (from Meta Cloud API):
    {
        "from": "1234567890",
        "id": "wamid.123...",
        "timestamp": "1234567890",
        "type": "text" | "image" | "document" | ...,
        "text": {"body": "Hello, world!"}
    }
    """
    message_id = payload.get("id", "unknown")
    from_number = payload.get("from", "unknown")
    timestamp = int(payload.get("timestamp", 0)) or int(time.time())
    message_type = payload.get("type", "text")

    # Extract text content based on message type
    text_content = ""
    if message_type == "text":
        text_content = payload.get("text", {}).get("body", "")
    elif message_type == "image":
        caption = payload.get("image", {}).get("caption", "")
        text_content = f"[Image] {caption}" if caption else "[Image]"
    elif message_type == "document":
        filename = payload.get("document", {}).get("filename", "document")
        text_content = f"[Document: {filename}]"
    else:
        text_content = f"[{message_type.upper()} message]"

    doc = Document(
        user_id=user_id,
        text=text_content,
        source="whatsapp",
        document_type="message",
        external_id=message_id,
        thread_id=from_number,  # Group messages from same contact
        created_at=timestamp,
        raw_metadata={
            "whatsapp_from": from_number,
            "whatsapp_type": message_type,
            "whatsapp_profile_name": payload.get("profile_name", "Unknown"),
        },
    )
    logger.info(
        "Normalized WhatsApp message id=%s from=%s user=%s",
        message_id, from_number, user_id,
    )
    return doc


def normalize_email(
    payload: dict[str, Any], user_id: str
) -> Document:
    """
    Normalize an inbound email (e.g., from SendGrid Inbound Parse).

    Expected payload structure:
    {
        "email_id": "unique-id",
        "subject": "Email Subject",
        "from": "sender@example.com",
        "text": "Email body (plain text)",
        "html": "Email body (HTML)",
        "timestamp": 1234567890
    }
    """
    email_id = payload.get("email_id", payload.get("id", "unknown"))
    from_addr = payload.get("from", "unknown")
    subject = payload.get("subject", "(no subject)")
    timestamp = int(payload.get("timestamp", 0)) or int(time.time())

    # Prefer plain text, fall back to HTML with minimal stripping
    text_body = payload.get("text", "")
    if not text_body:
        html_body = payload.get("html", "")
        # Simple HTML stripping (remove common tags)
        text_body = html_body.replace("<br>", "\n").replace("<br/>", "\n")
        text_body = text_body.replace("<p>", "").replace("</p>", "\n")
        text_body = text_body.replace("<div>", "").replace("</div>", "\n")

    # Combine subject and body for semantic search
    full_text = f"{subject}\n\n{text_body}".strip()

    doc = Document(
        user_id=user_id,
        text=full_text,
        source="gmail",
        document_type="message",
        external_id=email_id,
        thread_id=from_addr,  # Group emails from same sender
        created_at=timestamp,
        raw_metadata={
            "email_from": from_addr,
            "email_subject": subject,
            "email_to": payload.get("to", ""),
            "email_cc": payload.get("cc", ""),
        },
    )
    logger.info(
        "Normalized email id=%s from=%s subject=%s user=%s",
        email_id, from_addr, subject, user_id,
    )
    return doc


def normalize_calendar_event(
    payload: dict[str, Any], user_id: str
) -> Document:
    """
    Normalize a calendar event from Google Calendar API webhook.

    Expected payload structure:
    {
        "id": "event-id",
        "summary": "Event title",
        "description": "Event description",
        "start": {"dateTime": "2026-01-15T10:00:00Z"},
        "end": {"dateTime": "2026-01-15T11:00:00Z"},
        "attendees": [...]
    }
    """
    event_id = payload.get("id", "unknown")
    summary = payload.get("summary", "(no title)")
    description = payload.get("description", "")
    start = payload.get("start", {}).get("dateTime", "")

    # Extract timestamp from ISO string (simplified)
    timestamp = int(time.time())
    if start:
        try:
            # Parse ISO timestamp like "2026-01-15T10:00:00Z"
            from datetime import datetime
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            timestamp = int(dt.timestamp())
        except Exception:
            pass

    # Format event text for context
    attendee_count = len(payload.get("attendees", []))
    attendees_str = f" ({attendee_count} attendees)" if attendee_count else ""
    full_text = f"{summary}{attendees_str}\n\n{description}".strip()

    doc = Document(
        user_id=user_id,
        text=full_text,
        source="gcal",
        document_type="event",
        external_id=event_id,
        created_at=timestamp,
        raw_metadata={
            "event_summary": summary,
            "event_start": start,
            "event_end": payload.get("end", {}).get("dateTime", ""),
            "attendee_count": attendee_count,
        },
    )
    logger.info(
        "Normalized calendar event id=%s summary=%s user=%s",
        event_id, summary, user_id,
    )
    return doc

