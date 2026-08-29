"""Smoke coverage for read and mutation API endpoints."""
from tests.test_lifecycle import client  # noqa: F401


def test_core_endpoints(client):
    created = client.post("/runs?name=Endpoint-Line").json()
    run_id = created["id"]
    assert client.get("/runs").status_code == 200
    assert client.get(f"/runs/{run_id}").status_code == 200
    assert client.post(f"/runs/{run_id}/inject-fault").json()["ok"] is True
    assert client.get("/healthz").json()["status"] == "ok"
    readiness = client.get("/readyz").json()
    assert readiness["status"] in {"ready", "degraded"}
    assert set(readiness["checks"]) == {"database", "cv_service", "worker"}
    assert "runs_total" in client.get("/metrics").json()
    assert client.get("/runs/999999").status_code == 404
