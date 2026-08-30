"""CSV import and SQLite-backed analytics API coverage."""
from sqlmodel import Session, select

from app import db
from app.models import Event, Run, RunStatus, StepExecution, StepStatus, utcnow
from tests.test_lifecycle import client  # noqa: F401


def test_import_runs_from_csv(client):
    response = client.post(
        "/runs/import",
        content="name\nPrimary culture A\nPrimary culture B\n",
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200
    assert response.json() == {"created": 2}
    with Session(db.engine) as session:
        assert session.exec(select(Run.name).order_by(Run.name)).all() == [
            "Primary culture A", "Primary culture B",
        ]


def test_import_rejects_invalid_csv_without_partial_insert(client):
    response = client.post(
        "/runs/import",
        content="name\nValid line\nInvalid<line\n",
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 422
    with Session(db.engine) as session:
        assert session.exec(select(Run)).all() == []


def test_analytics_reports_only_persisted_run_and_event_counts(client):
    now = utcnow()
    with Session(db.engine) as session:
        session.add_all([
            Run(name="Ready", status=RunStatus.PENDING, current_stage=0),
            Run(name="Active", status=RunStatus.RUNNING, current_stage=2),
            Event(run_id=1, type="step_started", message="Seed"),
            Event(run_id=1, type="step_started", message="Incubate"),
            Event(run_id=2, type="imaged", message="Image complete"),
            StepExecution(run_id=2, stage_name="Seed", stage_kind="SEED", status=StepStatus.SUCCESS, started_at=now, finish_at=now),
        ])
        session.commit()

    payload = client.get("/analytics").json()

    assert payload["statuses"] == [
        {"label": "PENDING", "value": 1}, {"label": "RUNNING", "value": 1},
    ]
    assert payload["stages"] == [
        {"label": "Seed", "value": 1}, {"label": "Image", "value": 1},
    ]
    assert payload["events"] == [
        {"label": "imaged", "value": 1}, {"label": "step_started", "value": 2},
    ]
    assert payload["active_stages"] == [
        {"label": "Seed", "value": 1}, {"label": "Image", "value": 1},
    ]
    assert payload["stage_states"] == [
        {"label": "Seed", "active": 1, "running": 0, "waiting": 0, "paused": 0},
        {"label": "Incubate", "active": 0, "running": 0, "waiting": 0, "paused": 0},
        {"label": "Image", "active": 1, "running": 1, "waiting": 0, "paused": 0},
        {"label": "Count", "active": 0, "running": 0, "waiting": 0, "paused": 0},
        {"label": "Decision", "active": 0, "running": 0, "waiting": 0, "paused": 0},
        {"label": "Passage", "active": 0, "running": 0, "waiting": 0, "paused": 0},
    ]
    assert payload["summary"] == {
        "active_runs": 2,
        "completion_rate": None,
        "average_confluence": 0,
        "average_active_age_minutes": 0,
        "average_step_duration_minutes": 0.0,
        "events_last_24h": 3,
    }
    assert [event["run_name"] for event in payload["recent_events"]] == ["Active", "Ready", "Ready"]
