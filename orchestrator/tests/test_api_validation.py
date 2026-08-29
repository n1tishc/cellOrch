"""Validation tests for API mutation endpoints.

These tests verify that Pydantic request models reject invalid inputs with 422.
"""
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


def test_seed_rejects_zero(client):
    response = client.post("/seed?n=0")
    assert response.status_code == 422


def test_seed_rejects_negative(client):
    response = client.post("/seed?n=-1")
    assert response.status_code == 422


def test_seed_rejects_too_large(client):
    response = client.post("/seed?n=100001")
    assert response.status_code == 422


def test_seed_accepts_valid(client):
    response = client.post("/seed?n=10")
    assert response.status_code == 200
    assert response.json()["created"] == 10


def test_create_run_rejects_name_too_long(client):
    long_name = "x" * 101
    response = client.post(f"/runs?name={long_name}")
    assert response.status_code == 422


def test_create_run_rejects_invalid_characters(client):
    response = client.post("/runs?name=Bad<Name")
    assert response.status_code == 422


def test_create_run_accepts_valid_name(client):
    response = client.post("/runs?name=Good-Name_1")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Good-Name_1"
