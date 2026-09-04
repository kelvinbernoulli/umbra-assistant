from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.ingestion import (
    add_workspace_member,
    is_workspace_member,
    record_webhook_delivery,
    requeue_failed_job,
    resolve_api_key_user,
)
from app.db.models import Base, IngestionJob


def test_workspace_membership_is_scoped_to_workspace(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'membership.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        add_workspace_member(db, workspace_id="workspace-a", user_id="user-1")
        assert is_workspace_member(db, workspace_id="workspace-a", user_id="user-1")
        assert not is_workspace_member(db, workspace_id="workspace-b", user_id="user-1")
        assert not is_workspace_member(db, workspace_id="workspace-a", user_id="user-2")


def test_failed_job_can_be_requeued_until_attempt_limit(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'retry.db'}")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        job_id = record_webhook_delivery(
            db,
            workspace_id="workspace-retry",
            provider="gmail",
            external_id="message-1",
        )
        job = db.get(IngestionJob, job_id)
        job.status = "failed"
        job.attempts = 1
        db.commit()

        assert requeue_failed_job(db, job_id, max_attempts=3)
        assert db.get(IngestionJob, job_id).status == "queued"

        job.status = "failed"
        job.attempts = 3
        db.commit()
        assert not requeue_failed_job(db, job_id, max_attempts=3)
        assert db.get(IngestionJob, job_id).status == "failed"


def test_api_key_bootstrap_generates_a_resolvable_key(tmp_path, monkeypatch):
    from app.workers import provision_api_key as provision_api_key_worker

    engine = create_engine(f"sqlite:///{tmp_path / 'api-keys.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(provision_api_key_worker, "SessionLocal", sessions)

    key_id, raw_key = provision_api_key_worker.create_api_key(" user-1 ")

    with Session(engine) as db:
        assert key_id
        assert raw_key
        assert resolve_api_key_user(db, raw_key=raw_key) == "user-1"
        assert db.query(IngestionJob).count() == 0
