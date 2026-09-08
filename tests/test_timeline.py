from collections.abc import Generator
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.db.ingestion import add_workspace_member, provision_api_key
from app.db.models import Base, SourceItem, Workspace
from app.main import app


def test_timeline_is_workspace_scoped_and_ordered(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'timeline.db'}")
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
        provision_api_key(db, key_id="key-b", user_id="user-b", raw_key="api-key-b")
        add_workspace_member(db, workspace_id="workspace-a", user_id="user-a", role="owner")
        add_workspace_member(db, workspace_id="workspace-b", user_id="user-b", role="owner")
        db.add_all(
            [
                SourceItem(
                    id="a-old",
                    workspace_id="workspace-a",
                    source="gmail",
                    external_id="email-a-old",
                    document_type="message",
                    text="Older workspace A message",
                    payload_json='{"email_subject": "Older A"}',
                    created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                ),
                SourceItem(
                    id="a-new",
                    workspace_id="workspace-a",
                    source="gmail",
                    external_id="email-a-new",
                    document_type="message",
                    text="Newer workspace A message",
                    payload_json='{"email_subject": "Newer A"}',
                    created_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                ),
                SourceItem(
                    id="b-only",
                    workspace_id="workspace-b",
                    source="gmail",
                    external_id="email-b-only",
                    document_type="message",
                    text="Workspace B private message",
                    payload_json='{"email_subject": "Private B"}',
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
            response = client.get(
                "/api/v1/timeline?limit=1",
                headers={"X-API-Key": "api-key-a", "X-Workspace-ID": "workspace-a"},
            )

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": "a-new",
                "source": "gmail",
                "type": "message",
                "timestamp": "2025-01-02T00:00:00",
                "title": "Newer A",
                "detail": "Newer workspace A message",
            }
        ]
    finally:
        app.dependency_overrides.clear()


def test_timeline_requires_workspace_membership(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'timeline-auth.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    with Session(engine) as db:
        db.add(Workspace(id="workspace-a", name="Workspace A"))
        db.commit()
        provision_api_key(db, key_id="key-a", user_id="user-a", raw_key="api-key-a")

    def override_db() -> Generator[Session, None, None]:
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/timeline",
                headers={"X-API-Key": "api-key-a", "X-Workspace-ID": "workspace-a"},
            )
        assert response.status_code == 403
        assert response.json() == {"detail": "Workspace access denied"}
    finally:
        app.dependency_overrides.clear()
