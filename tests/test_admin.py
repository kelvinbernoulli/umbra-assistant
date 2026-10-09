import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.routes import admin
from app.core.config import settings
from app.db.auth_models import BrowserSession, GoogleUser
from app.db.models import ApiKey, Base, SourceItem, Workspace, WorkspaceIntegration, WorkspaceMember
from app.db.session import get_db
from app.services.browser_session import digest


def setup_admin(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ["admin@example.com"])
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def database():
        with factory() as db:
            yield db

    app = FastAPI()
    app.include_router(admin.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = database
    return engine, factory, TestClient(app), app


def add_user(factory, *, user_id, email, workspace_id):
    with factory() as db:
        db.add(Workspace(id=workspace_id, name=f"{email} workspace"))
        db.add(ApiKey(id=f"key-{user_id}", user_id=user_id, key_hash=f"hash-{user_id}"))
        db.flush()
        db.add(WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="owner"))
        db.add(
            GoogleUser(
                id=user_id,
                google_sub=f"sub-{user_id}",
                email=email,
                name=email.split("@")[0],
                workspace_id=workspace_id,
                api_key_id=f"key-{user_id}",
            )
        )
        db.commit()


def sign_in(client, factory, user_id):
    raw_token = f"session-{user_id}"
    with factory() as db:
        db.add(BrowserSession(
            token_hash=digest(raw_token),
            user_id=user_id,
            expires_at=int(time.time()) + 3600,
        ))
        db.commit()
    client.cookies.set("umbra_session", raw_token)


def test_admin_user_list_and_detail_expose_aggregate_data_only(monkeypatch):
    engine, factory, client, app = setup_admin(monkeypatch)
    try:
        add_user(factory, user_id="admin", email="Admin@Example.com", workspace_id="workspace-admin")
        add_user(factory, user_id="member", email="member@example.com", workspace_id="workspace-member")
        with factory() as db:
            db.add(WorkspaceIntegration(
                id="integration-1",
                workspace_id="workspace-member",
                provider="gmail",
                token_hash="integration-hash",
            ))
            db.add(SourceItem(
                id="item-1",
                workspace_id="workspace-member",
                source="gmail",
                external_id="private-external-id",
                document_type="email",
                text="private message body",
                payload_json='{"private":"metadata"}',
            ))
            db.commit()

        sign_in(client, factory, "admin")
        listing = client.get("/api/v1/admin/users")
        assert listing.status_code == 200
        assert listing.headers["cache-control"] == "no-store"
        assert listing.json()["total"] == 2
        member = next(item for item in listing.json()["items"] if item["user"]["id"] == "member")
        assert member["metrics"]["active_sources"] == 1
        assert member["metrics"]["stored_items"] == 1
        assert "private message body" not in listing.text

        detail = client.get("/api/v1/admin/users/member")
        assert detail.status_code == 200
        assert detail.json()["sources"] == [{"name": "gmail", "stored_items": 1}]
        assert detail.json()["metrics"]["stored_items"] == 1
        assert "private message body" not in detail.text
        assert "private-external-id" not in detail.text
        assert client.get("/api/v1/admin/users/missing").status_code == 404
    finally:
        app.dependency_overrides.clear()
        client.close()
        engine.dispose()


def test_admin_endpoints_reject_missing_and_non_admin_sessions(monkeypatch):
    engine, factory, client, app = setup_admin(monkeypatch)
    try:
        add_user(factory, user_id="member", email="member@example.com", workspace_id="workspace-member")
        assert client.get("/api/v1/admin/users").status_code == 401
        sign_in(client, factory, "member")
        assert client.get("/api/v1/admin/users").status_code == 403
        assert client.get("/api/v1/admin/users/member").status_code == 403
    finally:
        app.dependency_overrides.clear()
        client.close()
        engine.dispose()
