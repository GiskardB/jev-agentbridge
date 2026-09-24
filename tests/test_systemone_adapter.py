"""Tests for the System One adapter (kev / systemone engines) against a mocked HTTP layer."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from jev_agentbridge.adapters import registry
from jev_agentbridge.adapters.systemone.adapter import SystemOneAdapter, SystemOneConfig
from jev_agentbridge.core.errors import EngineError, EngineUnavailableError
from jev_agentbridge.core.models import Decision, Option
from jev_agentbridge.core.service import DecisionService

URLOPEN = "jev_agentbridge.adapters.systemone.adapter.urllib.request.urlopen"
RETRY_ABORT = (Option("retry", "Retry the deployment"), Option("abort", "Abort it"))


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def _choice(probabilities: dict) -> dict:
    best = max(probabilities, key=probabilities.get)
    return {"type": "choice", "choice": best, "confidence": 0.5, "probabilities": probabilities}


def _capture(monkeypatch: pytest.MonkeyPatch, answers: dict) -> list:
    sent: list = []

    def fake(request, timeout=None):
        sent.append(request)
        return _Response({"model": "kev-latest", "answers": answers, "latency_ms": 40})

    monkeypatch.setattr(URLOPEN, fake)
    return sent


def test_request_follows_the_system_one_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _capture(monkeypatch, {"decision": _choice({"retry": 0.8, "abort": 0.2})})
    config = SystemOneConfig(engine_name="kev", base_url="http://kev:8009/", model="kev-latest",
                             api_key="secret")
    scores = SystemOneAdapter(config).score(state={"k": 1}, decision=Decision("next?", RETRY_ABORT))

    request = sent[0]
    body = json.loads(request.data)
    assert request.full_url == "http://kev:8009/v1/systemone"
    assert request.get_header("Authorization") == "Bearer secret"
    assert body["model"] == "kev-latest"
    assert body["state"] == {"k": 1}
    assert body["questions"]["decision"] == {
        "type": "choice",
        "instructions": "next?",
        "criteria": {"retry": "Retry the deployment", "abort": "Abort it"},
    }
    assert scores.probabilities == {"retry": 0.8, "abort": 0.2}
    assert scores.details["confidence"] == 0.5


def test_batch_is_one_request(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _capture(
        monkeypatch,
        {"q0": _choice({"retry": 0.9, "abort": 0.1}), "q1": _choice({"yes": 0.3, "no": 0.7})},
    )
    service = DecisionService(SystemOneAdapter(SystemOneConfig()), default_threshold=0.6)
    results = service.decide_batch(
        state="s",
        decisions=[
            Decision("a?", RETRY_ABORT),
            Decision("b?", (Option("yes", "Y"), Option("no", "N"))),
        ],
    )
    assert [r.decision.id for r in results] == ["retry", "no"]
    assert len(sent) == 1
    assert "model" not in json.loads(sent[0].data)  # generic preset sends no model by default


def test_unreachable_server_is_engine_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(URLOPEN, refuse)
    with pytest.raises(EngineUnavailableError):
        SystemOneAdapter(SystemOneConfig()).score(state="s", decision=Decision("q", RETRY_ABORT))


def test_http_error_is_engine_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(request, timeout=None):
        # A real HTTPError from urlopen always carries a real (bytes-producing) fp; None
        # doesn't reproduce that (its .read() behavior isn't guaranteed across Python versions).
        raise urllib.error.HTTPError(
            request.full_url, 401, "unauthorized", {}, io.BytesIO(b"unauthorized")
        )

    monkeypatch.setattr(URLOPEN, reject)
    with pytest.raises(EngineError, match="401"):
        SystemOneAdapter(SystemOneConfig()).score(state="s", decision=Decision("q", RETRY_ABORT))


def test_kev_preset_reads_its_own_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JEV_KEV_URL", "http://gpu-box:8009")
    monkeypatch.setenv("JEV_KEV_MODEL", "kev-9b")
    info = registry.create_adapter("kev").info()
    assert (info.name, info.model, info.revision) == ("kev", "kev-9b", "http://gpu-box:8009")
    assert registry.create_adapter("systemone").info().name == "systemone"


def test_kev_preset_reports_pinned_model_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    # System One's response only ever carries a static model label ("kev-latest"), never the
    # actual checkpoint, so the operator has to say what they pinned the server to.
    pinned = "jaredpalmer/kev-0.8b@9a45d25eb2ab761841196625383fa1dff0e56c1e"
    monkeypatch.setenv("JEV_KEV_MODEL_REVISION", pinned)
    info = registry.create_adapter("kev").info()
    assert info.revision == pinned
