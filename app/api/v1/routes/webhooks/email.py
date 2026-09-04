"""
Version 1 inbound email webhook receiver — this is Phase 1's primary test target,
since it's easier to validate end-to-end without a WhatsApp Business
API approval in hand.

Designed for SendGrid Inbound Parse, which POST multipart/form-data.
This handler expects the payload to be parsed into a JSON schema beforehand
(either upstream via a middleware, or by SendGrid's JSON Parse webhook settings).

Expected JSON payload structure:
{
  "email_id": "unique-message-id@sendgrid.net",
  "from": "sender@example.com",
  "to": "myapp@example.com",
  "subject": "Email Subject",
  "text": "Plain text body",
  "html": "<html>...</html>",
  "timestamp": 1735500000
}
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.db.ingestion import (
    mark_job_failed,
    mark_job_processing,
    mark_job_succeeded,
    persist_source_item,
    record_webhook_delivery,
    resolve_webhook_workspace,
    verify_workspace_webhook_token,
)
from app.db.session import SessionLocal
from app.models.schemas.webhook_payloads import InboundEmail
from app.services.ingestion.normalizer import normalize_email
from app.services.ingestion.pipeline import ingest_documents

logger = get_logger(__name__)
router = APIRouter()


class WebhookAckResponse(BaseModel):
    """Simple 202 Accepted response for webhook validation."""

    status: str = "accepted"
    message: str = "Webhook received"


def _verify_sendgrid_signature(
    raw_body: bytes, signature_header: str | None
) -> None:
    """
    Verify SendGrid's signature if SENDGRID_INBOUND_SECRET is configured.

    Note: This is a simplified check against a custom header.
    For production, use SendGrid's official signature verification.
    """
    if not settings.SENDGRID_INBOUND_SECRET:
        logger.warning(
            "SENDGRID_INBOUND_SECRET not configured — skipping signature verification (dev only)"
        )
        return
    if not signature_header:
        raise ValueError("Missing signature header")
    if signature_header != settings.SENDGRID_INBOUND_SECRET:
        raise ValueError("Signature mismatch")


async def _process_email(email_payload: dict[str, Any], workspace_id: str, job_id: str) -> None:
    """Normalize email and queue for ingestion."""
    db = SessionLocal()
    try:
        logger.info("Processing email from=%s for workspace=%s job=%s", email_payload.get("from"), workspace_id, job_id)
        mark_job_processing(db, job_id)
        doc = normalize_email(email_payload, workspace_id)
        persist_source_item(db, workspace_id=workspace_id, document=doc)
        await ingest_documents([doc])
        mark_job_succeeded(db, job_id)
        logger.info("Successfully queued email for ingestion: %s", email_payload.get("email_id"))
    except Exception as exc:  # noqa: BLE001
        logger.error("Error processing email: %s", exc, exc_info=True)
        try:
            mark_job_failed(db, job_id, str(exc))
        except Exception:  # noqa: BLE001
            logger.error("Could not mark ingestion job failed: %s", job_id, exc_info=True)
    finally:
        db.close()


@router.post("/webhooks/email", status_code=202)
async def receive_email_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_inbound_signature: str | None = Header(default=None),
    x_workspace_id: str | None = Header(default=None),
    x_workspace_token: str | None = Header(default=None),
) -> WebhookAckResponse:
    """
    Receive and validate incoming email via SendGrid Inbound Parse.

    Steps:
      1. Verify signature (if SENDGRID_INBOUND_SECRET configured)
      2. Parse JSON payload
      3. Queue for background ingestion
      4. Return 202 Accepted immediately

    This keeps the endpoint non-blocking even under burst traffic.
    """
    raw_body = await request.body()

    # Verify signature
    try:
        _verify_sendgrid_signature(raw_body, x_inbound_signature)
    except ValueError as exc:
        logger.warning("Signature verification failed: %s", exc)
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    # Parse payload
    try:
        import json

        payload = json.loads(raw_body)
    except Exception as exc:
        logger.error("Failed to parse email webhook JSON: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    # Validate against InboundEmail schema
    try:
        email_schema = InboundEmail.model_validate(payload)
    except ValidationError as exc:
        logger.error("Email payload validation failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid email payload") from exc

    # Canonicalize legacy aliases before the payload reaches the normalizer.
    email_payload = email_schema.model_dump(by_alias=True)
    db = SessionLocal()
    try:
        workspace_id = resolve_webhook_workspace(db, provider="gmail", token=x_workspace_token)
        if workspace_id is None:
            raise HTTPException(status_code=403, detail="Workspace webhook authentication failed")
        if x_workspace_id and x_workspace_id.strip() != workspace_id:
            raise HTTPException(status_code=403, detail="Workspace webhook authentication failed")
        job_id = record_webhook_delivery(
            db,
            workspace_id=workspace_id,
            provider="gmail",
            external_id=email_payload["email_id"],
        )
    finally:
        db.close()

    if job_id is None:
        logger.info("Duplicate email webhook ignored: workspace=%s external_id=%s", workspace_id, email_payload["email_id"])
        return WebhookAckResponse(message="Email already received")

    # Queue background task
    background_tasks.add_task(_process_email, email_payload, workspace_id, job_id)

    logger.info("Email webhook received and queued: from=%s", email_payload.get("from"))
    return WebhookAckResponse(message="Email received and queued for processing")
