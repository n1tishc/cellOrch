"""Tests for the global error handler and structured logging setup."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

os.environ.setdefault("DB_URL", "sqlite:///:memory:")
os.environ.setdefault("SEED_ON_START", "0")
os.environ.setdefault("TICK_INTERVAL", "1000")

from app import db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    """Yield a TestClient backed by a fresh in-memory database."""
    original_engine = db.engine
    db.engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db.init_db()
    try:
        with TestClient(app) as c:
            yield c
    finally:
        db.engine = original_engine


def test_error_envelope(client, monkeypatch):
    """Unhandled endpoint exceptions return the consistent ErrorResponse shape."""
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.main.seed_runs", boom)
    response = client.post("/seed?n=5")

    assert response.status_code == 500
    data = response.json()
    assert data["error"] == "internal_error"
    assert "detail" in data
    assert "request_id" in data


def test_http_exceptions_not_swallowed(client):
    """HTTPExceptions (404) are still returned with their proper status."""
    response = client.get("/runs/999999")
    assert response.status_code == 404
    assert "X-Request-ID" in response.headers
