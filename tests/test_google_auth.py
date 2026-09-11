from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select


from app.services import google_connections as store
from app.api.v1.routes import auth, connections


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(connections, "list_sources", lambda: [{"name": "gcal"}, {"name": "gmail"}])
    monkeypatch.setattr(auth.settings, "GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setattr(auth.settings, "GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(auth.settings, "CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(auth.settings, "CREDENTIAL_DB_URL", f"sqlite:///{tmp_path / 'credentials.db'}")
    flow = Mock()
    flow.credentials = SimpleNamespace(refresh_token="private-refresh-token")
    factory = Mock(return_value=flow)
    monkeypatch.setattr(auth.Flow, "from_client_config", factory)
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(connections.router, prefix="/api/v1")

    def current_user(x_api_key: str | None = Header(None)):
        if x_api_key not in {"user-one", "user-two"}:
            raise HTTPException(401, "Missing or invalid API key")
        return x_api_key

    app.dependency_overrides[auth.get_current_user_id] = current_user
    with TestClient(app) as client:
        yield client, flow, factory
    store.get_engine().dispose()


def headers(user="user-one"):
    return {"X-API-Key": user, "Origin": "http://localhost:5173", "X-Requested-With": "XmlHttpRequest"}


def test_exchange_persists_encrypted_credentials_and_reports_status(setup):
    client, flow, factory = setup
    response = client.post("/api/v1/auth/google/save", json={"code": "one-use-code"}, headers=headers())
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "private-refresh-token" not in response.text
    assert factory.call_args.kwargs["redirect_uri"] == "http://localhost:5173"
    flow.fetch_token.assert_called_once_with(code="one-use-code", timeout=20)
    with store.get_engine().connect() as connection:
        encrypted = connection.scalar(select(store.credentials.c.encrypted_token))
    assert "private-refresh-token" not in encrypted
    assert store.cipher().decrypt(encrypted.encode()).decode() == "private-refresh-token"
    statuses = client.get("/api/v1/connections", headers=headers()).json()
    assert next(item for item in statuses if item["provider"] == "gcal")["status"] == "connected"
    other = client.get("/api/v1/connections", headers=headers("user-two")).json()
    assert next(item for item in other if item["provider"] == "gcal")["status"] == "disconnected"


@pytest.mark.parametrize("changes, status", [
    ({"X-API-Key": "bad"}, 401),
    ({"Origin": "https://untrusted.example"}, 403),
    ({"X-Requested-With": "bad"}, 403),
])
def test_invalid_requests_do_not_exchange_codes(setup, changes, status):
    client, _, factory = setup
    response = client.post("/api/v1/auth/google/save", json={"code": "code"}, headers=headers() | changes)
    assert response.status_code == status
    factory.assert_not_called()


def test_client_cannot_choose_another_user(setup):
    client, _, factory = setup
    response = client.post("/api/v1/auth/google/save", json={"code": "code", "user_id": "user-two"}, headers=headers())
    assert response.status_code == 422
    factory.assert_not_called()


def test_missing_refresh_token_does_not_claim_success(setup):
    client, flow, _ = setup
    flow.credentials.refresh_token = None
    response = client.post("/api/v1/auth/google/save", json={"code": "code"}, headers=headers())
    assert response.status_code == 400
    assert store.list_statuses("user-one") == []


def test_invalid_storage_key_fails_before_exchange(setup, monkeypatch):
    client, _, factory = setup
    monkeypatch.setattr(auth.settings, "CREDENTIAL_ENCRYPTION_KEY", "invalid")
    response = client.post("/api/v1/auth/google/save", json={"code": "code"}, headers=headers())
    assert response.status_code == 503
    factory.assert_not_called()


def test_exchange_errors_do_not_expose_secrets(setup):
    client, flow, _ = setup
    flow.fetch_token.side_effect = RuntimeError("private-refresh-token test-secret")
    response = client.post("/api/v1/auth/google/save", json={"code": "code"}, headers=headers())
    assert response.status_code == 400
    assert "private-refresh-token" not in response.text
    assert "test-secret" not in response.text


def test_disconnect_only_removes_current_users_connection(setup):
    client, _, _ = setup
    store.save_refresh_token("user-one", "token-one")
    store.save_refresh_token("user-two", "token-two")
    response = client.post("/api/v1/connections/gcal/disconnect", headers=headers())
    assert response.status_code == 200
    assert store.list_statuses("user-one") == []
    assert len(store.list_statuses("user-two")) == 1
