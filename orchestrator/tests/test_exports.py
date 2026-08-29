"""Integration tests for CSV and JSON run-data exports."""
import csv
import io
import json

from sqlmodel import Session

from app import db
from app.models import Event, StepExecution, StepStatus
from tests.test_lifecycle import client  # noqa: F401


def test_single_run_exports_csv_and_json(client):
    run_id = client.post("/runs?name=Export-Line").json()["id"]
    with Session(db.engine) as session:
        session.add(Event(run_id=run_id, type="step_done", message="Seed complete"))
        session.add(StepExecution(run_id=run_id, stage_name="Seed", stage_kind="SEED", status=StepStatus.SUCCESS))
        session.commit()

    csv_response = client.get(f"/runs/{run_id}/export?format=csv")
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert f"run_{run_id}.csv" in csv_response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(csv_response.text)))
    assert {row["record_type"] for row in rows} == {"run", "step", "event"}

    json_response = client.get(f"/runs/{run_id}/export?format=json")
    payload = json.loads(json_response.content)
    assert json_response.headers["content-disposition"] == f'attachment; filename="run_{run_id}.json"'
    assert payload["run"]["id"] == run_id
    assert len(payload["steps"]) == 1 and len(payload["events"]) == 1


def test_all_runs_export_includes_each_run(client):
    client.post("/runs?name=Export-One")
    client.post("/runs?name=Export-Two")

    response = client.get("/runs/export?format=csv")
    assert response.status_code == 200
    assert {"Export-One", "Export-Two"} <= {
        row["name"] for row in csv.DictReader(io.StringIO(response.text))
    }
    assert response.headers["content-disposition"] == 'attachment; filename="runs.csv"'
    json_response = client.get("/runs/export?format=json")
    assert json_response.headers["content-disposition"] == 'attachment; filename="runs.json"'
    assert {"Export-One", "Export-Two"} <= {run["name"] for run in json_response.json()}
