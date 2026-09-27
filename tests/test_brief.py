from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.routes import brief as routes
from app.db.ingestion import add_workspace_member, provision_api_key
from app.db.models import Base, SourceItem, Workspace


@pytest.fixture
def brief(tmp_path, monkeypatch):
    monkeypatch.setattr(routes.settings, "BRIEF_AI_ENABLED", False)
    engine = create_engine(f"sqlite:///{tmp_path / 'brief.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Workspace(id="a", name="A"), Workspace(id="b", name="B")])
        db.commit()
        provision_api_key(db, key_id="key-a", user_id="alice", raw_key="alice-key")
        add_workspace_member(db, workspace_id="a", user_id="alice", role="owner")
        db.add_all([
            SourceItem(id="a1", workspace_id="a", source="gmail", external_id="1",
                       document_type="email", text="My email"),
            SourceItem(id="b1", workspace_id="b", source="manual", external_id="2",
                       document_type="reminder", text="Other workspace secret"),
        ])
        db.commit()
    app = FastAPI()
    app.include_router(routes.router)

    def database():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[routes.get_db] = database
    google = Mock(return_value={"items": []})
    monkeypatch.setattr(routes, "calendar_request", google)
    # Missing AI services must not prevent a brief.
    monkeypatch.setenv("PINECONE_API_KEY", "")
    with TestClient(app) as client:
        yield client, google
    engine.dispose()


HEADERS = {"X-API-Key": "alice-key", "X-Workspace-ID": "a"}


def test_brief_uses_live_events_and_scoped_saved_activity(brief):
    client, google = brief
    google.return_value = {"items": [
        {"id": "1", "summary": "Planning", "start": {"dateTime": "2026-09-25T10:00:00+01:00"}},
        {"id": "2", "summary": "Day off", "start": {"date": "2026-09-25"}},
        {"id": "3", "status": "cancelled", "summary": "Cancelled"},
    ]}
    response = client.get("/brief/today?timezone=Africa/Lagos", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["calendar_count"] == 2
    assert "Planning; Day off" in data["summary"]
    assert "1 messages or emails and 0 reminders" in data["summary"]
    assert "secret" not in response.text
    assert data["calendar_notice"] is None
    assert google.call_args.args == ("alice", "GET")
    assert google.call_args.kwargs["params"]["timeMin"].endswith("T00:00:00+01:00")


def test_brief_requires_auth_and_workspace_membership(brief):
    client, google = brief
    assert client.get("/brief/today").status_code == 401
    assert client.get("/brief/today", headers=HEADERS | {"X-Workspace-ID": "b"}).status_code == 403
    google.assert_not_called()


@pytest.mark.parametrize("status", [403, 409, 429, 502, 503])
def test_unavailable_calendar_is_not_reported_as_empty(brief, status):
    client, google = brief
    google.side_effect = HTTPException(status, "Reconnect or retry Calendar.")
    data = client.get("/brief/today", headers=HEADERS).json()
    assert data["calendar_count"] is None
    assert data["calendar_notice"] == "Reconnect or retry Calendar."
    assert "No events" not in data["summary"]
    assert "1 messages or emails" in data["summary"]


def test_empty_and_paginated_calendar(brief):
    client, google = brief
    data = client.get("/brief/today", headers=HEADERS).json()
    assert data["calendar_count"] == 0
    assert "No events" in data["summary"]
    google.return_value = {"items": [{"id": str(i), "summary": "Meeting"} for i in range(4)], "nextPageToken": "next"}
    data = client.get("/brief/today", headers=HEADERS).json()
    assert data["calendar_has_more"] is True
    assert len(data["calendar_events"]) == 3
    assert "at least 4 events" in data["summary"]


def test_timezone_validation_and_dst_day(brief, monkeypatch):
    client, google = brief
    assert client.get("/brief/today?timezone=Invalid/Zone", headers=HEADERS).status_code == 422
    google.assert_not_called()

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 8, 16, tzinfo=timezone.utc)

    monkeypatch.setattr(routes, "datetime", Clock)
    assert client.get("/brief/today?timezone=America/New_York", headers=HEADERS).status_code == 200
    params = google.call_args.kwargs["params"]
    assert params["timeMin"] == "2026-03-08T00:00:00-05:00"
    assert params["timeMax"] == "2026-03-09T00:00:00-04:00"
