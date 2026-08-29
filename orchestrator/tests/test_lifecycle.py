"""Lifecycle API and scheduler tests for pausing, resuming, and cancelling runs."""
import os
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

os.environ.setdefault("DB_URL", "sqlite:///:memory:")
os.environ.setdefault("SEED_ON_START", "0")
os.environ.setdefault("TICK_INTERVAL", "1000")
os.environ.setdefault("FAILURE_RATE", "0")

from app import db, engine, protocol  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Run, RunStatus, StepExecution, StepStatus  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    original_engine = db.engine
    monkeypatch.setattr(db.settings, "db_url", "sqlite:///:memory:")
    db.engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db.init_db()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        db.engine = original_engine


def start_running_run(run: Run, now: datetime) -> int:
    with Session(db.engine) as session:
        session.add(run)
        session.commit()
        session.refresh(run)
        assert run.id is not None
        engine.tick(session, now=now)
        return run.id


def test_paused_run_does_not_advance_and_resume_restarts_it(client):
    now = datetime(2026, 1, 1)
    run_id = start_running_run(Run(name="Pause me"), now)

    assert client.post(f"/runs/{run_id}/pause").status_code == 200
    with Session(db.engine) as session:
        paused = session.get(Run, run_id)
        assert paused.status == RunStatus.PAUSED
        stage = paused.current_stage
        engine.tick(session, now=now + timedelta(days=1))
        assert session.get(Run, run_id).current_stage == stage

    assert client.post(f"/runs/{run_id}/resume").status_code == 200
    with Session(db.engine) as session:
        engine.tick(session, now=now + timedelta(days=1))
        assert session.get(Run, run_id).status == RunStatus.RUNNING


def test_cancelling_resource_holder_frees_resource_for_waiting_run(client):
    now = datetime(2026, 1, 1)
    first = Run(name="First", current_stage=protocol.STAGE_INDEX[protocol.IMAGE])
    second = Run(name="Second", current_stage=protocol.STAGE_INDEX[protocol.IMAGE])
    with Session(db.engine) as session:
        session.add_all([first, second])
        session.commit()
        engine.tick(session, now=now)
        session.refresh(first)
        session.refresh(second)
        assert first.status == RunStatus.RUNNING
        assert second.status == RunStatus.WAITING

    assert client.post(f"/runs/{first.id}/cancel").status_code == 200
    with Session(db.engine) as session:
        assert session.get(Run, first.id).status == RunStatus.CANCELLED
        assert session.exec(select(StepExecution).where(StepExecution.run_id == first.id)).one().status == StepStatus.CANCELLED
        engine.tick(session, now=now + timedelta(seconds=1))
        assert session.get(Run, second.id).status == RunStatus.RUNNING


def test_lifecycle_api_rejects_invalid_transitions(client):
    with Session(db.engine) as session:
        completed = Run(name="Done", status=RunStatus.COMPLETED)
        pending = Run(name="Pending")
        session.add_all([completed, pending])
        session.commit()
        session.refresh(completed)
        session.refresh(pending)

    assert client.post(f"/runs/{completed.id}/pause").status_code == 400
    assert client.post(f"/runs/{pending.id}/resume").status_code == 400
    assert client.post("/runs/999999/cancel").status_code == 404
