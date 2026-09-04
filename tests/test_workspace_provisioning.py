from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.main import app
from app.db.ingestion import (
    add_workspace_member,
    provision_api_key,
    provision_workspace_webhook_token,
    verify_workspace_webhook_token,
)
from app.db.models import Base, Workspace


def test_workspace_owner_can_bootstrap_and_rotate_webhook_token(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'workspace.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as db:
        provision_api_key(db, key_id="key-user-1", user_id="user-1", raw_key="api-key-user-1")

    def override_db() -> Generator[Session, None, None]:
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            first = client.post(
                "/api/v1/workspaces/workspace-a/webhook-token",
                headers={"X-API-Key": "api-key-user-1"},
            )
            second = client.post(
                "/api/v1/workspaces/workspace-a/webhook-token",
                headers={"X-API-Key": "api-key-user-1"},
            )

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["token"] != second.json()["token"]
        with Session(engine) as db:
            assert db.get(Workspace, "workspace-a").webhook_token_hash
            assert verify_workspace_webhook_token(
                db, workspace_id="workspace-a", token=second.json()["token"]
            )
            assert not verify_workspace_webhook_token(
                db, workspace_id="workspace-a", token=first.json()["token"]
            )
    finally:
        app.dependency_overrides.clear()


def test_workspace_member_cannot_rotate_webhook_token(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'workspace.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as db:
        provision_api_key(db, key_id="key-owner", user_id="owner", raw_key="api-key-owner")
        provision_api_key(db, key_id="key-member", user_id="member", raw_key="api-key-member")
        db.add(Workspace(id="workspace-a", name="Workspace A"))
        db.commit()
        add_workspace_member(db, workspace_id="workspace-a", user_id="owner", role="owner")
        add_workspace_member(db, workspace_id="workspace-a", user_id="member", role="member")
        provision_workspace_webhook_token(db, workspace_id="workspace-a", token="original-token")

    def override_db() -> Generator[Session, None, None]:
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/workspaces/workspace-a/webhook-token",
                headers={"X-API-Key": "api-key-member"},
            )
        assert response.status_code == 403
        assert response.json() == {"detail": "Workspace administration denied"}
    finally:
        app.dependency_overrides.clear()


def test_unknown_api_key_is_rejected(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'workspace.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Generator[Session, None, None]:
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/workspaces/workspace-a/webhook-token",
                headers={"X-API-Key": "not-provisioned"},
            )
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid API key"}
    finally:
        app.dependency_overrides.clear()
