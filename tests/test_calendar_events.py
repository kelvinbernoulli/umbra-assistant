from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from google.auth.exceptions import RefreshError

from app.api.v1.routes import calendar_events as routes
from app.services import google_calendar as service, google_connections as store


@pytest.fixture
def calendar(tmp_path, monkeypatch):
    monkeypatch.setattr(store.settings, "CREDENTIAL_DB_URL", f"sqlite:///{tmp_path / 'calendar.db'}")
    monkeypatch.setattr(store.settings, "CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(store.settings, "GOOGLE_CLIENT_ID", "client")
    monkeypatch.setattr(store.settings, "GOOGLE_CLIENT_SECRET", "secret")
    store.save_refresh_token("alice", "alice-private-token")
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    session.request.return_value = Mock(status_code=200, ok=True)
    session.request.return_value.json.return_value = {"id": "event-1", "summary": "Planning"}
    factory = Mock(return_value=session)
    monkeypatch.setattr(service, "AuthorizedSession", factory)
    app = FastAPI()
    app.include_router(routes.router)

    def identity(x_api_key: str | None = Header(None)):
        if x_api_key not in {"alice", "bob"}:
            raise HTTPException(401, "Sign in")
        return x_api_key

    app.dependency_overrides[routes.get_current_user_id] = identity
    with TestClient(app) as client:
        yield client, session, factory
    store.get_engine().dispose()


def event():
    return {"summary": "Planning", "start": {"dateTime": "2026-10-01T10:00:00+01:00"},
            "end": {"dateTime": "2026-10-01T11:00:00+01:00"}}


def test_create_uses_authenticated_users_encrypted_token(calendar):
    client, session, factory = calendar
    response = client.post("/calendar/events", json=event(), headers={"X-API-Key": "alice"})
    assert response.status_code == 201
    assert response.json()["id"] == "event-1"
    assert factory.call_args.args[0].refresh_token == "alice-private-token"
    assert session.request.call_args.args == ("POST", "https://www.googleapis.com/calendar/v3/calendars/primary/events")
    assert session.request.call_args.kwargs["json"] == event()
    assert "private" not in response.text


def test_other_user_cannot_use_connection(calendar):
    client, _, factory = calendar
    assert client.post("/calendar/events", json=event(), headers={"X-API-Key": "bob"}).status_code == 409
    assert client.post("/calendar/events", json=event()).status_code == 401
    assert client.post("/calendar/events", json=event() | {"user_id": "alice"}, headers={"X-API-Key": "bob"}).status_code == 422
    factory.assert_not_called()


def test_patch_only_sends_supplied_fields(calendar):
    client, session, _ = calendar
    response = client.patch("/calendar/events/event-1?calendar_id=team%40example.com", json={"location": ""}, headers={"X-API-Key": "alice"})
    assert response.status_code == 200
    assert session.request.call_args.args == ("PATCH", "https://www.googleapis.com/calendar/v3/calendars/team%40example.com/events/event-1")
    assert session.request.call_args.kwargs["json"] == {"location": ""}


@pytest.mark.parametrize("body", [
    {}, {"summary": ""}, {"summary": None}, {"start": {"date": "2026-10-01"}},
    {"start": {"date": "2026-10-02"}, "end": {"date": "2026-10-01"}},
    {"start": {"dateTime": "2026-10-01T10:00:00"}, "end": {"dateTime": "2026-10-01T11:00:00"}},
    {"start": {"date": "2026-10-01"}, "end": {"dateTime": "2026-10-02T10:00:00Z"}},
])
def test_invalid_patch_never_calls_google(calendar, body):
    client, _, factory = calendar
    assert client.patch("/calendar/events/event-1", json=body, headers={"X-API-Key": "alice"}).status_code == 422
    factory.assert_not_called()


def test_all_day_event(calendar):
    client, session, _ = calendar
    body = {"summary": "Day off", "start": {"date": "2026-10-01"}, "end": {"date": "2026-10-02"}}
    assert client.post("/calendar/events", json=body, headers={"X-API-Key": "alice"}).status_code == 201
    assert session.request.call_args.kwargs["json"] == body


def test_list_returns_pagination(calendar):
    client, session, _ = calendar
    session.request.return_value.json.return_value = {"items": [], "nextPageToken": "next"}
    response = client.get("/calendar/events?page_token=previous&limit=10", headers={"X-API-Key": "alice"})
    assert response.json() == {"items": [], "nextPageToken": "next"}
    assert session.request.call_args.kwargs["params"]["pageToken"] == "previous"


@pytest.mark.parametrize("upstream, expected", [(401, 409), (403, 403), (404, 404), (429, 429), (500, 502)])
def test_google_errors_are_sanitized(calendar, upstream, expected):
    client, session, _ = calendar
    session.request.return_value.status_code = upstream
    session.request.return_value.ok = False
    session.request.return_value.text = "private-token"
    response = client.post("/calendar/events", json=event(), headers={"X-API-Key": "alice"})
    assert response.status_code == expected
    assert "private-token" not in response.text


def test_revoked_refresh_token_requires_reconnect(calendar):
    client, session, _ = calendar
    session.request.side_effect = RefreshError("private-token")
    response = client.get("/calendar/events", headers={"X-API-Key": "alice"})
    assert response.status_code == 409
    assert "private-token" not in response.text


@pytest.mark.parametrize("reason,field,status,message", [
    ("accessNotConfigured", "errors", 503, "API is disabled"),
    ("SERVICE_DISABLED", "details", 503, "API is disabled"),
    ("insufficientPermissions", "errors", 403, "read permission"),
    ("ACCESS_TOKEN_SCOPE_INSUFFICIENT", "details", 403, "read permission"),
    ("rateLimitExceeded", "errors", 429, "request limit"),
    ("domainPolicy", "errors", 403, "administrator"),
    ("unknown", "errors", 403, "read access"),
])
def test_read_errors_explain_the_actual_google_reason(calendar, reason, field, status, message):
    client, session, _ = calendar
    response = session.request.return_value
    response.status_code = 403
    response.ok = False
    response.json.return_value = {"error": {field: [{"reason": reason, "message": "private-token"}]}}
    result = client.get("/calendar/events", headers={"X-API-Key": "alice"})
    assert result.status_code == status
    assert message in result.json()["detail"]
    assert "editable" not in result.text
    assert "private-token" not in result.text


@pytest.mark.parametrize("payload", [None, [], {"error": "bad"}, {"error": {"errors": None}}, {"error": {"errors": [None, {"reason": []}]}}])
def test_malformed_google_error_still_has_a_safe_message(calendar, payload):
    client, session, _ = calendar
    session.request.return_value.status_code = 403
    session.request.return_value.json.return_value = payload
    response = client.get("/calendar/events", headers={"X-API-Key": "alice"})
    assert response.status_code == 403
    assert "read access" in response.json()["detail"]
