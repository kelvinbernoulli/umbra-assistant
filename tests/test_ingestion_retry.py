import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.ingestion import mark_job_failed, persist_source_item, record_webhook_delivery
from app.db.models import Base, IngestionJob
from app.models.domain.document import Document
from app.services.ingestion import retry


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'retry.db'}")
    Base.metadata.create_all(engine)
    return engine


def test_retry_reconstructs_persisted_source_item(database, monkeypatch):
    sessions = sessionmaker(bind=database, expire_on_commit=False)
    with Session(database) as db:
        job_id = record_webhook_delivery(
            db,
            workspace_id="workspace-retry",
            provider="gmail",
            external_id="message-1",
        )
        document = Document(
            user_id="workspace-retry",
            text="Persisted email text",
            source="gmail",
            document_type="message",
            external_id="message-1",
            created_at=1735500000,
            raw_metadata={"email_subject": "Retry me"},
        )
        persist_source_item(db, workspace_id="workspace-retry", document=document)
        mark_job_failed(db, job_id, "temporary failure")

    ingest_documents = AsyncMock()
    monkeypatch.setattr(retry, "ingest_documents", ingest_documents)
    assert asyncio.run(retry.retry_ingestion_job(job_id, sessions))

    ingest_documents.assert_awaited_once()
    retried_document = ingest_documents.await_args.args[0][0]
    assert retried_document.external_id == "message-1"
    assert retried_document.text == "Persisted email text"
    with Session(database) as db:
        assert db.get(IngestionJob, job_id).status == "succeeded"
        assert db.get(IngestionJob, job_id).attempts == 1


def test_retry_does_not_exceed_attempt_limit(database, monkeypatch):
    sessions = sessionmaker(bind=database, expire_on_commit=False)
    with Session(database) as db:
        job_id = record_webhook_delivery(
            db,
            workspace_id="workspace-exhausted",
            provider="gmail",
            external_id="message-2",
        )
        job = db.get(IngestionJob, job_id)
        job.status = "failed"
        job.attempts = 3
        db.commit()

    ingest_documents = AsyncMock()
    monkeypatch.setattr(retry, "ingest_documents", ingest_documents)
    assert not asyncio.run(retry.retry_ingestion_job(job_id, sessions))
    ingest_documents.assert_not_awaited()


def test_retry_worker_selects_only_jobs_with_remaining_budget(database, monkeypatch):
    sessions = sessionmaker(bind=database, expire_on_commit=False)
    with Session(database) as db:
        retryable_id = record_webhook_delivery(
            db,
            workspace_id="workspace-worker",
            provider="gmail",
            external_id="message-retryable",
        )
        persist_source_item(
            db,
            workspace_id="workspace-worker",
            document=Document(
                user_id="workspace-worker",
                text="Retryable text",
                source="gmail",
                document_type="message",
                external_id="message-retryable",
                created_at=1735500000,
            ),
        )
        retryable = db.get(IngestionJob, retryable_id)
        retryable.status = "failed"
        retryable.attempts = 1
        db.commit()
        exhausted_id = record_webhook_delivery(
            db,
            workspace_id="workspace-worker",
            provider="gmail",
            external_id="message-exhausted",
        )
        exhausted = db.get(IngestionJob, exhausted_id)
        exhausted.status = "failed"
        exhausted.attempts = 3
        db.commit()

    ingest_documents = AsyncMock()
    monkeypatch.setattr(retry, "ingest_documents", ingest_documents)
    result = asyncio.run(retry.run_retry_worker(sessions, limit=10))

    assert result == {"selected": 1, "succeeded": 1, "failed": 0}
    ingest_documents.assert_awaited_once()
