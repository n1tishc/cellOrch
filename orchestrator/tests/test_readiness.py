"""Deep readiness checks report dependency and worker health."""
from app import main
from app.models import utcnow
from tests.test_lifecycle import client  # noqa: F401


def test_readyz_reports_cv_unreachable_and_worker_stalled(client, monkeypatch):
    def unreachable(*args, **kwargs):
        raise main.httpx.ConnectError("down")

    monkeypatch.setattr(main.httpx, "get", unreachable)
    monkeypatch.setattr(main, "last_worker_tick", None)

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "checks": {"database": "ok", "cv_service": "unreachable", "worker": "stalled"},
    }


def test_readyz_is_ready_when_dependencies_and_worker_are_healthy(client, monkeypatch):
    class Response:
        is_success = True

    monkeypatch.setattr(main.httpx, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(main, "last_worker_tick", utcnow())

    assert client.get("/deep-healthz").json()["status"] == "ok"
