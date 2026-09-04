from __future__ import annotations

import json
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.ingestion import (
    get_ingestion_job,
    mark_job_failed,
    mark_job_processing,
    mark_job_succeeded,
    requeue_failed_job,
)
from app.db.models import IngestionJob, SourceItem
from app.models.domain.document import Document
from app.services.ingestion.pipeline import ingest_documents


async def retry_ingestion_job(job_id: str, sessions: sessionmaker[Session]) -> bool:
    """Retry one failed job from its durable canonical source item."""
    db = sessions()
    try:
        job = get_ingestion_job(db, job_id)
        if job is None or not requeue_failed_job(
            db, job_id, max_attempts=settings.MAX_INGESTION_ATTEMPTS
        ):
            return False

        item = db.scalar(
            select(SourceItem).where(
                SourceItem.workspace_id == job.workspace_id,
                SourceItem.external_id == job.receipt.external_id,
            )
        )
        if item is None:
            raise LookupError(f"Source item for ingestion job '{job_id}' does not exist")

        mark_job_processing(db, job_id)
        document = Document(
            user_id=job.workspace_id,
            text=item.text,
            source=item.source,
            document_type=item.document_type,
            id=item.id,
            external_id=item.external_id,
            created_at=int(item.created_at.replace(tzinfo=timezone.utc).timestamp()),
            raw_metadata=json.loads(item.payload_json or "{}"),
        )
        await ingest_documents([document])
        mark_job_succeeded(db, job_id)
        return True
    except Exception as exc:  # noqa: BLE001
        if get_ingestion_job(db, job_id) is not None:
            db.rollback()
            mark_job_failed(db, job_id, str(exc))
        return False
    finally:
        db.close()


async def run_retry_worker(
    sessions: sessionmaker[Session], *, limit: int = 100
) -> dict[str, int]:
    """Retry a bounded batch of failed jobs and return execution counts."""
    if limit < 1:
        raise ValueError("Retry worker limit must be greater than zero")

    db = sessions()
    try:
        job_ids = list(
            db.scalars(
                select(IngestionJob.id)
                .where(
                    IngestionJob.status == "failed",
                    IngestionJob.attempts < settings.MAX_INGESTION_ATTEMPTS,
                )
                .order_by(IngestionJob.created_at)
                .limit(limit)
            )
        )
    finally:
        db.close()

    succeeded = 0
    for job_id in job_ids:
        if await retry_ingestion_job(job_id, sessions):
            succeeded += 1
    return {
        "selected": len(job_ids),
        "succeeded": succeeded,
        "failed": len(job_ids) - succeeded,
    }