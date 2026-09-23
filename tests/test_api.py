"""HTTP contract tests: the same responses whatever adapter sits behind the service."""

from __future__ import annotations

from fastapi.testclient import TestClient

from jev_cpu_agentbridge.main import app, create_app
from jev_cpu_agentbridge.runtime.settings import Settings
from tests.conftest import FakeAdapter

OPTIONS = [{"id": "retry", "description": "Retry"}, {"id": "abort", "description": "Abort"}]


def _client(adapter: FakeAdapter | None = None, threshold: float = 0.6) -> TestClient:
    return TestClient(
        create_app(Settings(min_selected_probability=threshold), adapter or FakeAdapter())
    )


def test_health() -> None:
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_ready_before_engine_loaded() -> None:
    r = TestClient(app).get("/ready")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "MODEL_NOT_READY"


def test_decide_before_engine_loaded_is_503() -> None:
    r = TestClient(app).post("/v1/decide", json={"state": "s", "question": "q", "options": OPTIONS})
    assert r.status_code == 503


def test_ready_and_info() -> None:
    client = _client()
    ready = client.get("/ready").json()
    assert ready == {"status": "ready", "engine": "fake", "model": "fake-model"}
    info = client.get("/v1/info").json()
    assert info["api_version"] == "v1"
    assert info["engine"]["name"] == "fake"
    assert info["default_min_selected_probability"] == 0.6
    assert {"semif", "laya", "rizzoflow"} <= set(info["available_engines"])


def test_decide_standard_response() -> None:
    r = _client().post("/v1/decide", json={"state": "s", "question": "q", "options": OPTIONS})
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == {"id": "retry", "description": "Retry"}
    assert set(body["probabilities"]) == {"retry", "abort"}
    assert body["accepted"] is True
    assert body["threshold"] == 0.6
    assert body["metadata"]["engine"] == "fake"


def test_decide_per_request_threshold() -> None:
    r = _client(FakeAdapter(top=0.7)).post(
        "/v1/decide",
        json={"state": "s", "criterion": "q", "options": OPTIONS, "min_selected_probability": 0.9},
    )
    assert r.json()["accepted"] is False
    assert r.json()["threshold"] == 0.9


def test_batch_threshold_precedence() -> None:
    r = _client(FakeAdapter(top=0.7)).post(
        "/v1/decide/batch",
        json={
            "state": "s",
            "min_selected_probability": 0.8,
            "decisions": [
                {"question": "q1", "options": OPTIONS},
                {"question": "q2", "options": OPTIONS, "min_selected_probability": 0.5},
            ],
        },
    )
    assert r.status_code == 200
    assert [d["threshold"] for d in r.json()["decisions"]] == [0.8, 0.5]
    assert [d["accepted"] for d in r.json()["decisions"]] == [False, True]


def test_validation_errors_use_the_error_envelope() -> None:
    client = _client()
    too_few = client.post(
        "/v1/decide", json={"state": "s", "question": "q", "options": OPTIONS[:1]}
    )
    assert too_few.status_code == 422
    assert too_few.json()["error"]["code"] == "INVALID_REQUEST"
    too_many = client.post(
        "/v1/decide",
        json={
            "state": "s",
            "question": "q",
            "options": [{"id": str(i), "description": str(i)} for i in range(17)],
        },
    )
    assert too_many.status_code == 422
    bad_threshold = client.post(
        "/v1/decide",
        json={"state": "s", "question": "q", "options": OPTIONS, "min_selected_probability": 2},
    )
    assert bad_threshold.status_code == 422


def test_duplicate_option_ids() -> None:
    r = _client().post(
        "/v1/decide",
        json={"state": "s", "question": "q", "options": [OPTIONS[0], OPTIONS[0]]},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "DUPLICATE_OPTION_ID"


def test_engine_failure_is_500_with_envelope() -> None:
    adapter = FakeAdapter()
    adapter.error = RuntimeError("boom")
    body = {"state": "s", "question": "q", "options": OPTIONS}
    r = _client(adapter).post("/v1/decide", json=body)
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "ENGINE_ERROR"
    assert r.json()["error"]["request_id"]


def test_openapi_published() -> None:
    paths = _client().get("/openapi.json").json()["paths"]
    assert {"/v1/decide", "/v1/decide/batch", "/v1/info", "/health", "/ready"} <= set(paths)
