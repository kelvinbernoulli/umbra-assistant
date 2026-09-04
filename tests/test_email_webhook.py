from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.ingestion import provision_workspace_webhook_token


DOCUMENTED_EMAIL_PAYLOAD = {
    "email_id": "test-email-123@sendgrid.net",
    "from": "sender@example.com",
    "to": "myapp@example.com",
    "subject": "Test Email",
    "text": "This is the plain-text body.",
    "html": "<p>This is the HTML body.</p>",
    "timestamp": 1735500000,
}


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch, tmp_path):
    from app.api.v1.routes.webhooks import email

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(email, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    with sessionmaker(bind=engine)() as db:
        provision_workspace_webhook_token(
            db, workspace_id="workspace-email-test", token="workspace-token-email-test"
        )
        provision_workspace_webhook_token(
            db, workspace_id="workspace-email-invalid", token="workspace-token-email-invalid"
        )


def _load_email_routes(monkeypatch):
    # Prevent repository-local environment settings from activating real services
    # while this route contract is tested.
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("DATABASE_URL", "disabled")
    monkeypatch.setenv("PINECONE_API_KEY", "test-disabled")
    monkeypatch.setenv("HUGGINGFACE_API_TOKEN", "test-disabled")

    from app.api.v1.routes.webhooks import email

    return email


def test_email_webhook_accepts_documented_payload(monkeypatch):
    email_routes = _load_email_routes(monkeypatch)
    ingest_documents = AsyncMock(return_value=["chunk-1"])

    monkeypatch.setattr(email_routes.settings, "SENDGRID_INBOUND_SECRET", "test-secret")
    monkeypatch.setattr(email_routes, "ingest_documents", ingest_documents)

    app = FastAPI()
    app.include_router(email_routes.router, prefix="/api/v1")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/webhooks/email",
            json=DOCUMENTED_EMAIL_PAYLOAD,
            headers={"X-Inbound-Signature": "test-secret", "X-Workspace-ID": "workspace-email-test", "X-Workspace-Token": "workspace-token-email-test"},
        )

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "message": "Email received and queued for processing",
    }
    ingest_documents.assert_awaited_once()

    await_args = ingest_documents.await_args
    assert await_args is not None
    documents = await_args.args[0]
    assert len(documents) == 1

    document = documents[0]
    assert document.user_id == "workspace-email-test"
    assert document.source == "gmail"
    assert document.document_type == "message"
    assert document.external_id == DOCUMENTED_EMAIL_PAYLOAD["email_id"]
    assert document.thread_id == DOCUMENTED_EMAIL_PAYLOAD["from"]
    assert document.created_at == DOCUMENTED_EMAIL_PAYLOAD["timestamp"]
    assert document.text == "Test Email\n\nThis is the plain-text body."
    assert document.raw_metadata == {
        "email_from": "sender@example.com",
        "email_subject": "Test Email",
        "email_to": "myapp@example.com",
        "email_cc": "",
    }


def test_email_webhook_rejects_payload_without_provider_id(monkeypatch):
    email_routes = _load_email_routes(monkeypatch)
    ingest_documents = AsyncMock(return_value=["chunk-1"])

    monkeypatch.setattr(email_routes.settings, "SENDGRID_INBOUND_SECRET", "test-secret")
    monkeypatch.setattr(email_routes, "ingest_documents", ingest_documents)

    payload = {
        key: value
        for key, value in DOCUMENTED_EMAIL_PAYLOAD.items()
        if key != "email_id"
    }

    app = FastAPI()
    app.include_router(email_routes.router, prefix="/api/v1")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/webhooks/email",
            json=payload,
            headers={"X-Inbound-Signature": "test-secret", "X-Workspace-ID": "workspace-email-invalid", "X-Workspace-Token": "workspace-token-email-invalid"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid email payload"}
    ingest_documents.assert_not_awaited()


def test_email_schema_canonicalizes_legacy_field_names(monkeypatch):
    _load_email_routes(monkeypatch)

    from app.models.schemas.webhook_payloads import InboundEmail

    email = InboundEmail.model_validate(
        {
            "id": "legacy-message-id",
            "sender": "legacy-sender@example.com",
            "to": "inbox@example.com",
            "subject": None,
            "body": "Legacy body",
            "timestamp": "1735500000",
        }
    )

    assert email.model_dump(by_alias=True) == {
        "email_id": "legacy-message-id",
        "from": "legacy-sender@example.com",
        "to": "inbox@example.com",
        "subject": "(no subject)",
        "text": "Legacy body",
        "html": "",
        "timestamp": 1735500000,
        "cc": "",
    }
