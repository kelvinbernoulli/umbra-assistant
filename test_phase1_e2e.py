"""Isolated Phase 1 API contract tests."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.models import Base
from app.db.models import IngestionJob, SourceItem
from app.db.ingestion import provision_workspace_webhook_token


EMAIL_PAYLOAD = {
    "email_id": "test-email-123@sendgrid.net",
    "from": "sender@example.com",
    "to": "myapp@example.com",
    "subject": "Test Email",
    "text": "This is the plain-text body.",
    "timestamp": 1735500000,
}


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch, tmp_path):
    from app.api.v1.routes.webhooks import email

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(email, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    with sessionmaker(bind=engine)() as db:
        for workspace_id in ("workspace-test", "workspace-duplicate", "workspace-failed"):
            provision_workspace_webhook_token(
                db, workspace_id=workspace_id, token=f"workspace-token-{workspace_id}"
            )
    yield engine
    engine.dispose()


def test_app_health_is_available():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_valid_email_webhook_is_accepted_without_external_services(monkeypatch, isolated_database):
    from app.api.v1.routes.webhooks import email

    ingest_documents = AsyncMock()
    monkeypatch.setattr(email.settings, "SENDGRID_INBOUND_SECRET", "test-secret")
    monkeypatch.setattr(email, "ingest_documents", ingest_documents)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/webhooks/email",
            json=EMAIL_PAYLOAD,
            headers={"X-Inbound-Signature": "test-secret", "X-Workspace-ID": "workspace-test", "X-Workspace-Token": "workspace-token-workspace-test"},
        )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    ingest_documents.assert_awaited_once()

    with sessionmaker(bind=isolated_database)() as db:
        assert db.query(SourceItem).one().workspace_id == "workspace-test"
        assert db.query(IngestionJob).one().status == "succeeded"


def test_invalid_email_payload_is_rejected_and_not_ingested(monkeypatch):
    from app.api.v1.routes.webhooks import email

    ingest_documents = AsyncMock()
    monkeypatch.setattr(email.settings, "SENDGRID_INBOUND_SECRET", "test-secret")
    monkeypatch.setattr(email, "ingest_documents", ingest_documents)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/webhooks/email",
            json={"to": "myapp@example.com"},
            headers={"X-Inbound-Signature": "test-secret", "X-Workspace-ID": "workspace-test", "X-Workspace-Token": "workspace-token-workspace-test"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid email payload"}
    ingest_documents.assert_not_awaited()


def test_invalid_email_signature_is_rejected_and_not_ingested(monkeypatch):
    from app.api.v1.routes.webhooks import email

    ingest_documents = AsyncMock()
    monkeypatch.setattr(email.settings, "SENDGRID_INBOUND_SECRET", "test-secret")
    monkeypatch.setattr(email, "ingest_documents", ingest_documents)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/webhooks/email",
            json=EMAIL_PAYLOAD,
            headers={"X-Inbound-Signature": "wrong-secret", "X-Workspace-ID": "workspace-test", "X-Workspace-Token": "workspace-token-workspace-test"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Signature mismatch"}
    ingest_documents.assert_not_awaited()


def test_invalid_workspace_token_is_rejected_and_not_recorded(monkeypatch, isolated_database):
    from app.api.v1.routes.webhooks import email

    ingest_documents = AsyncMock()
    monkeypatch.setattr(email.settings, "SENDGRID_INBOUND_SECRET", "test-secret")
    monkeypatch.setattr(email, "ingest_documents", ingest_documents)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/webhooks/email",
            json=EMAIL_PAYLOAD,
            headers={
                "X-Inbound-Signature": "test-secret",
                "X-Workspace-ID": "workspace-test",
                "X-Workspace-Token": "wrong-token",
            },
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Workspace webhook authentication failed"}
    ingest_documents.assert_not_awaited()


def test_duplicate_email_webhook_is_accepted_without_a_second_job(monkeypatch):
    from app.api.v1.routes.webhooks import email

    ingest_documents = AsyncMock()
    monkeypatch.setattr(email.settings, "SENDGRID_INBOUND_SECRET", "test-secret")
    monkeypatch.setattr(email, "ingest_documents", ingest_documents)

    headers = {"X-Inbound-Signature": "test-secret", "X-Workspace-ID": "workspace-duplicate", "X-Workspace-Token": "workspace-token-workspace-duplicate"}
    with TestClient(app) as client:
        first = client.post("/api/v1/webhooks/email", json=EMAIL_PAYLOAD, headers=headers)
        second = client.post("/api/v1/webhooks/email", json=EMAIL_PAYLOAD, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["message"] == "Email already received"
    ingest_documents.assert_awaited_once()


def test_failed_ingestion_is_recorded_on_the_job(monkeypatch, isolated_database):
    from app.api.v1.routes.webhooks import email

    ingest_documents = AsyncMock(side_effect=RuntimeError("embedding unavailable"))
    monkeypatch.setattr(email.settings, "SENDGRID_INBOUND_SECRET", "test-secret")
    monkeypatch.setattr(email, "ingest_documents", ingest_documents)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/webhooks/email",
            json=EMAIL_PAYLOAD,
            headers={"X-Inbound-Signature": "test-secret", "X-Workspace-ID": "workspace-failed", "X-Workspace-Token": "workspace-token-workspace-failed"},
        )

    assert response.status_code == 202
    with sessionmaker(bind=isolated_database)() as db:
        job = db.query(IngestionJob).one()
        assert job.status == "failed"
        assert job.attempts == 1
        assert job.last_error == "embedding unavailable"