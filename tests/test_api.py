"""Integration tests for the FastAPI API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jev_cpu_agentbridge.main import app


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_not_initialized() -> None:
    client = TestClient(app)
    r = client.get("/ready")
    assert r.status_code == 503


def test_info() -> None:
    client = TestClient(app)
    r = client.get("/v1/info")
    assert r.status_code == 200
    assert r.json()["engine"] == "semif"


def test_decide_invalid_options_count() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/decide",
        json={
            "state": "test",
            "question": "which?",
            "options": [{"id": "a", "description": "A"}],
        },
    )
    assert r.status_code == 422


def test_decide_too_many_options() -> None:
    client = TestClient(app)
    r = client.post(
        "/v1/decide",
        json={
            "state": "test",
            "question": "which?",
            "options": [{"id": str(i), "description": str(i)} for i in range(17)],
        },
    )
    assert r.status_code == 422


def test_batch_invalid_options() -> None:
    """Test that batch with single-option decision fails validation."""
    client = TestClient(app)
    r = client.post(
        "/v1/decide/batch",
        json={
            "state": "test",
            "decisions": [
                {"state": "test", "question": "which?", "options": [{"id": "a", "description": "A"}]}
            ],
        },
    )
    assert r.status_code == 422