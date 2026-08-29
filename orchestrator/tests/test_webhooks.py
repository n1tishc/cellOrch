"""Webhook API and delivery selection tests."""
import json

from app import engine, webhooks
from app.db import get_session
from app.models import Webhook
from tests.test_lifecycle import client  # noqa: F401


def test_webhook_test_endpoint_dispatches_selected_hook(client, monkeypatch):
    created = client.post("/webhooks", json={"url": "https://example.test/hook", "events": ["run.failed"]}).json()
    deliveries = []
    monkeypatch.setattr("app.main.dispatch_webhook", lambda url, payload: deliveries.append((url, payload)))

    response = client.post(f"/webhooks/{created['id']}/test")

    assert response.json() == {"ok": True, "webhook_id": created["id"]}
    assert deliveries[0][0] == "https://example.test/hook"
    assert deliveries[0][1]["event_type"] == "webhook.test"


def test_failed_run_events_match_run_failed_subscription(client, monkeypatch):
    deliveries = []
    monkeypatch.setattr(webhooks, "dispatch_webhook", lambda url, payload: deliveries.append((url, payload)))
    with get_session() as session:
        hook = Webhook(url="https://example.test/failures", events=json.dumps(["run.failed"]))
        session.add(hook)
        session.commit()
        engine.log(session, 42, "failed", "Run failed")

    assert deliveries == [("https://example.test/failures", {
        "event_type": "run.failed", "run_id": 42, "message": "Run failed", "timestamp": deliveries[0][1]["timestamp"],
    })]
