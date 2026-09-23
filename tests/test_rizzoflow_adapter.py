"""Tests for the RizzoFlow adapter against a mocked HTTP layer (no real server)."""

from __future__ import annotations

import json
import urllib.error

import pytest

from jev_cpu_agentbridge.adapters.rizzoflow.adapter import RizzoFlowAdapter
from jev_cpu_agentbridge.core.errors import EngineUnavailableError
from jev_cpu_agentbridge.core.models import Decision, Option
from jev_cpu_agentbridge.core.service import DecisionService

URLOPEN = "jev_cpu_agentbridge.adapters.rizzoflow.adapter.urllib.request.urlopen"
RETRY_ABORT = (Option("retry", "Retry"), Option("abort", "Abort"))


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def _payload(answers: dict) -> dict:
    return {"model": {}, "mode": "direct", "answers": answers, "calibration": None, "timing": {}}


def _answer(choice: str | None, probabilities: dict) -> dict:
    return {"status": "ok", "probabilities": probabilities, "choice": choice}


def _mock(monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
    monkeypatch.setattr(URLOPEN, lambda request, timeout=None: _FakeResponse(payload))


def test_score_maps_probabilities_and_drops_internal_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock(monkeypatch, _payload({"decision": _answer("retry", {"retry": 0.81, "abort": 0.19,
                                                               "__abstain__": 0.0})}))
    scores = RizzoFlowAdapter(base_url="http://x").score(
        state="test", decision=Decision("which?", RETRY_ABORT)
    )
    assert scores.probabilities == {"retry": 0.81, "abort": 0.19}
    assert scores.details["status"] == "ok"


def test_service_picks_argmax_even_with_null_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock(monkeypatch, _payload({"decision": _answer(None, {"retry": 0.6, "abort": 0.4})}))
    service = DecisionService(RizzoFlowAdapter(base_url="http://x"), default_threshold=0.5)
    result = service.decide(state="test", decision=Decision("which?", RETRY_ABORT))
    assert result.decision.id == "retry"
    assert result.metadata["engine"] == "rizzoflow"


def test_score_batch_maps_each_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock(
        monkeypatch,
        _payload(
            {
                "0": _answer("retry", {"retry": 0.9, "abort": 0.1}),
                "1": _answer("no", {"yes": 0.2, "no": 0.8}),
            }
        ),
    )
    results = RizzoFlowAdapter(base_url="http://x").score_batch(
        state="test",
        decisions=[
            Decision("which?", RETRY_ABORT),
            Decision("notify?", (Option("yes", "Yes"), Option("no", "No"))),
        ],
    )
    assert [max(r.probabilities, key=r.probabilities.get) for r in results] == ["retry", "no"]


def test_unreachable_server_is_engine_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(URLOPEN, refuse)
    with pytest.raises(EngineUnavailableError):
        RizzoFlowAdapter(base_url="http://x").score(
            state="test", decision=Decision("which?", RETRY_ABORT)
        )
