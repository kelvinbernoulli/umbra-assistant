"""
Version 1 WhatsApp webhook receiver.

Two responsibilities of a webhook route, and only these two:
  1. Validate (signature/verify-token) fast.
  2. Hand off to background processing and return immediately.
Never do embedding/upserting inline in the request path — that's what
keeps this endpoint non-blocking under burst traffic.

Meta sends webhooks with this structure:
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "entry-id",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "1234567890",
              "phone_number_id": "...",
              "business_account_id": "..."
            },
            "contacts": [...],
            "messages": [
              {
                "from": "1234567890",
                "id": "wamid.123...",
                "timestamp": "1234567890",
                "type": "text",
                "text": {"body": "Hello"}
              }
            ]
          }
        }
      ]
    }
  ]
}
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import WebhookSignatureError
from app.core.logging import get_logger
from app.services.ingestion.normalizer import normalize_whatsapp_message
from app.services.ingestion.pipeline import ingest_documents

logger = get_logger(__name__)
router = APIRouter()


class WebhookAckResponse(BaseModel):
    """Simple 202 Accepted response for webhook validation."""

    status: str = "accepted"
    message: str = "Webhook received"


def _verify_signature(raw_body: bytes, signature_header: str | None) -> None:
    """Verify X-Hub-Signature-256 header against WHATSAPP_APP_SECRET."""
    if not settings.WHATSAPP_APP_SECRET:
        logger.warning(
            "WHATSAPP_APP_SECRET not configured — skipping signature verification (dev only)"
        )
        return
    if not signature_header:
        raise WebhookSignatureError("Missing X-Hub-Signature-256 header")

    expected = "sha256=" + hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise WebhookSignatureError("Signature mismatch")


def _extract_messages_and_user_id(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """
    Extract all messages and user_id from Meta webhook payload.

    For now, user_id is derived from the phone_number_id. In production, this should
    be mapped to an actual user via a phone → user mapping table or OAuth context.
    """
    messages: list[dict[str, Any]] = []
    user_id = "default-user"  # Placeholder

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            # Extract metadata for user_id (phone_number_id maps to a user)
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id", "unknown")
            # In production: look up user_id from phone_number_id
            user_id = f"user-{phone_number_id}"

            # Extract all messages in this change
            msgs = value.get("messages", [])
            messages.extend(msgs)

    return messages, user_id


async def _process_messages(messages: list[dict[str, Any]], user_id: str) -> None:
    """Normalize messages and queue for ingestion."""
    if not messages:
        logger.info("Received WhatsApp webhook with no messages")
        return

    logger.info("Processing %d WhatsApp messages for user=%s", len(messages), user_id)

    try:
        # Normalize each message into a Document
        docs = [normalize_whatsapp_message(msg, user_id) for msg in messages]
        # Queue for ingestion (includes chunking, embedding, upsert)
        await ingest_documents(docs)
        logger.info("Successfully queued %d documents for ingestion", len(docs))
    except Exception as exc:  # noqa: BLE001
        logger.error("Error processing WhatsApp messages: %s", exc, exc_info=True)
        # Don't re-raise — webhook validation succeeded, errors here are async


@router.get("/webhooks/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    """Meta's webhook verification handshake (GET request on setup)."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verification successful")
        return int(hub_challenge)
    logger.warning(
        "WhatsApp webhook verification failed: mode=%s token_match=%s",
        hub_mode,
        hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN,
    )
    raise HTTPException(status_code=403, detail="Verification token mismatch")


@router.post("/webhooks/whatsapp", status_code=202)
async def receive_whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
) -> WebhookAckResponse:
    """
    Receive and validate incoming WhatsApp messages.

    Steps:
      1. Verify X-Hub-Signature-256 (fast, synchronous)
      2. Parse and extract messages
      3. Queue for background ingestion (chunking, embedding, upsert)
      4. Return 202 Accepted immediately

    This keeps the endpoint non-blocking even under burst traffic.
    """
    raw_body = await request.body()

    # Validate signature
    try:
        _verify_signature(raw_body, x_hub_signature_256)
    except WebhookSignatureError as exc:
        logger.warning("Signature verification failed: %s", exc.message)
        raise HTTPException(status_code=403, detail=exc.message) from exc

    # Parse payload
    try:
        import json

        payload = json.loads(raw_body)
    except Exception as exc:
        logger.error("Failed to parse webhook JSON: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    # Extract messages and derive user_id
    messages, user_id = _extract_messages_and_user_id(payload)

    # Queue background task
    background_tasks.add_task(_process_messages, messages, user_id)

    logger.info("Webhook received and queued for processing: %d messages", len(messages))
    return WebhookAckResponse(message=f"Received {len(messages)} message(s)")
