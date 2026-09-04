from __future__ import annotations

import json
import hashlib
import hmac
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ApiKey, IngestionJob, SourceItem, WebhookReceipt, Workspace, WorkspaceIntegration
from app.db.models import WorkspaceMember
from app.models.domain.document import Document


def record_webhook_delivery(
    db: Session,
    *,
    workspace_id: str,
    provider: str,
    external_id: str,
) -> str | None:
    """Create a workspace, receipt, and queued job in one transaction.

    Returns the job id for a new delivery and None when the delivery was already seen.
    """
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        workspace = Workspace(id=workspace_id, name=workspace_id)
        db.add(workspace)

    receipt = WebhookReceipt(
        id=str(uuid4()),
        workspace_id=workspace_id,
        provider=provider,
        external_id=external_id,
    )
    db.add(receipt)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(WebhookReceipt.id).where(
                WebhookReceipt.workspace_id == workspace_id,
                WebhookReceipt.provider == provider,
                WebhookReceipt.external_id == external_id,
            )
        )
        if existing is None:
            raise
        return None

    job = IngestionJob(
        id=str(uuid4()),
        workspace_id=workspace_id,
        receipt_id=receipt.id,
        status="queued",
        attempts=0,
    )
    db.add(job)
    db.commit()
    return job.id


def provision_workspace_webhook_token(db: Session, *, workspace_id: str, token: str) -> None:
    if not token:
        raise ValueError("Webhook token cannot be empty")
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        workspace = Workspace(id=workspace_id, name=workspace_id)
        db.add(workspace)
    workspace.webhook_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    integration = db.scalar(
        select(WorkspaceIntegration).where(
            WorkspaceIntegration.workspace_id == workspace_id,
            WorkspaceIntegration.provider == "gmail",
        )
    )
    if integration is None:
        integration = WorkspaceIntegration(
            id=str(uuid4()), workspace_id=workspace_id, provider="gmail", token_hash=workspace.webhook_token_hash
        )
        db.add(integration)
    else:
        integration.token_hash = workspace.webhook_token_hash
        integration.active = True
    db.commit()


def verify_workspace_webhook_token(db: Session, *, workspace_id: str, token: str | None) -> bool:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or not token or not workspace.webhook_token_hash:
        return False
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return hmac.compare_digest(workspace.webhook_token_hash, token_hash)


def resolve_webhook_workspace(db: Session, *, provider: str, token: str | None) -> str | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    integration = db.scalar(
        select(WorkspaceIntegration).where(
            WorkspaceIntegration.provider == provider,
            WorkspaceIntegration.token_hash == token_hash,
            WorkspaceIntegration.active.is_(True),
        )
    )
    return integration.workspace_id if integration else None


def mark_job_processing(db: Session, job_id: str) -> None:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise LookupError(f"Ingestion job '{job_id}' does not exist")
    job.status = "processing"
    job.attempts += 1
    db.commit()


def get_ingestion_job(db: Session, job_id: str) -> IngestionJob | None:
    return db.get(IngestionJob, job_id)


def persist_source_item(db: Session, *, workspace_id: str, document: Document) -> None:
    item = SourceItem(
        id=document.id,
        workspace_id=workspace_id,
        source=str(document.source),
        external_id=document.external_id or document.id,
        document_type=str(document.document_type),
        text=document.text,
        payload_json=json.dumps(document.raw_metadata, sort_keys=True),
        created_at=datetime.fromtimestamp(document.created_at, tz=timezone.utc),
    )
    db.add(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def mark_job_succeeded(db: Session, job_id: str) -> None:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise LookupError(f"Ingestion job '{job_id}' does not exist")
    job.status = "succeeded"
    job.last_error = None
    db.commit()


def mark_job_failed(db: Session, job_id: str, error: str) -> None:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise LookupError(f"Ingestion job '{job_id}' does not exist")
    job.status = "failed"
    job.last_error = error[:4000]
    db.commit()


def requeue_failed_job(db: Session, job_id: str, *, max_attempts: int = 3) -> bool:
    """Requeue a failed job when it still has retry budget."""
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise LookupError(f"Ingestion job '{job_id}' does not exist")
    if job.status != "failed" or job.attempts >= max_attempts:
        return False
    job.status = "queued"
    db.commit()
    return True


def add_workspace_member(db: Session, *, workspace_id: str, user_id: str, role: str = "member") -> None:
    db.merge(WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role))
    db.commit()


def is_workspace_member(db: Session, *, workspace_id: str, user_id: str) -> bool:
    return db.get(WorkspaceMember, (workspace_id, user_id)) is not None


def get_workspace_member_role(db: Session, *, workspace_id: str, user_id: str) -> str | None:
    member = db.get(WorkspaceMember, (workspace_id, user_id))
    return member.role if member else None


def provision_api_key(db: Session, *, key_id: str, user_id: str, raw_key: str) -> None:
    if not raw_key:
        raise ValueError("API key cannot be empty")
    db.add(ApiKey(
        id=key_id,
        user_id=user_id,
        key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
    ))
    db.commit()


def resolve_api_key_user(db: Session, *, raw_key: str) -> str | None:
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    key = db.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.active.is_(True)))
    return key.user_id if key else None