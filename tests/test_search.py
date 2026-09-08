from collections.abc import Generator
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.db.ingestion import add_workspace_member, provision_api_key
from app.db.models import Base, SourceItem, Workspace
from app.main import app


def test_search_is_workspace_scoped_and_supports_filters(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'search.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    with Session(engine) as db:
        db.add_all(
            [
                Workspace(id="workspace-a", name="Workspace A"),
                Workspace(id="workspace-b", name="Workspace B"),
            ]
        )
        db.commit()
        provision_api_key(db, key_id="key-a", user_id="user-a", raw_key="api-key-a")
        add_workspace_member(db, workspace_id="workspace-a", user_id="user-a", role="owner")
        db.add_all(
            [
                SourceItem(
                    id="a-email",
                    workspace_id="workspace-a",
                    source="gmail",
                    external_id="email-a",
                    document_type="message",
                    text="Project alpha meeting notes",
                    created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                ),
                SourceItem(
                    id="a-event",
                    workspace_id="workspace-a",
                    source="gcal",
                    external_id="event-a",
                    document_type="event",
                    text="Project alpha calendar event",
                    created_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                ),
                SourceItem(
                    id="b-private",
                    workspace_id="workspace-b",
                    source="gmail",
                    external_id="email-b",
                    document_type="message",
                    text="Project alpha private message",
                    created_at=datetime(2025, 1, 3, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()

    def override_db() -> Generator[Session, None, None]:
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/search",
                json={"query": "ALPHA", "source": "gmail", "document_type": "message"},
                headers={"X-API-Key": "api-key-a", "X-Workspace-ID": "workspace-a"},
            )

        assert response.status_code == 200
        assert response.json() == [
            {"id": "a-email", "snippet": "Project alpha meeting notes"}
        ]
    finally:
        app.dependency_overrides.clear()


def test_search_rejects_invalid_limit(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'search-limit.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    with Session(engine) as db:
        db.add(Workspace(id="workspace-a", name="Workspace A"))
        db.commit()
        provision_api_key(db, key_id="key-a", user_id="user-a", raw_key="api-key-a")
        add_workspace_member(db, workspace_id="workspace-a", user_id="user-a", role="owner")

    def override_db() -> Generator[Session, None, None]:
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/search",
                json={"query": "anything", "limit": 101},
                headers={"X-API-Key": "api-key-a", "X-Workspace-ID": "workspace-a"},
            )
        assert response.status_code == 400
        assert response.json() == {"detail": "Search limit must be between 1 and 100"}
    finally:
        app.dependency_overrides.clear()
