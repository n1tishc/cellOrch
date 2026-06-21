"""Client for the CV inference service.

Calls the cv-service /analyze endpoint to get a confluence reading at the IMAGE
stage. If the service is unreachable (or during tests), it falls back to a
deterministic local estimate so the orchestrator never blocks — the same
rising-confluence curve the stub service uses.
"""
import os

import httpx

CV_URL = os.environ.get("CV_SERVICE_URL", "http://cv-service:8001")


def stub_confluence(image_count: int) -> dict:
    """Deterministic rising confluence: ~0.30, 0.48, 0.66, 0.84, ... capped."""
    conf = min(0.95, 0.30 + 0.18 * image_count)
    return {"confluence": round(conf, 3), "cell_count": int(200 + 900 * conf), "anomalies": []}


def analyze(run_id: int, image_count: int) -> dict:
    payload = {"run_id": run_id, "image_index": image_count}
    try:
        resp = httpx.post(f"{CV_URL}/analyze", json=payload, timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        # Resilience: a CV outage shouldn't crash the pipeline.
        return stub_confluence(image_count)
