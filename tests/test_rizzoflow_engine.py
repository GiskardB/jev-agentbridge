"""Tests for RizzoFlowEngine against a mocked HTTP layer (no real server)."""

from __future__ import annotations

import json

import pytest

from jev_cpu_agentbridge.engine.base import Option
from jev_cpu_agentbridge.engine.rizzoflow import RizzoFlowEngine


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def _choice_payload(answers: dict) -> dict:
    return {
        "model": {},
        "mode": "direct",
        "answers": answers,
        "calibration": None,
        "timing": {},
    }


def _choice_answer(choice: str, probabilities: dict) -> dict:
    return {
        "status": "ok",
        "probabilities": probabilities,
        "choice": choice,
    }


def test_decide_maps_choice_and_probabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _choice_payload(
        {"decision": _choice_answer("retry", {"retry": 0.81, "abort": 0.19})}
    )
    monkeypatch.setattr(
        "jev_cpu_agentbridge.engine.rizzoflow.urllib.request.urlopen",
        lambda request, timeout=None: _FakeResponse(payload),
    )
    engine = RizzoFlowEngine(base_url="http://localhost:8017", min_selected_probability=0.5)

    result = engine.decide(
        state="test",
        question="which?",
        options=[Option(id="retry", description="Retry"), Option(id="abort", description="Abort")],
    )

    assert result.decision.id == "retry"
    assert result.selected_probability == 0.81
    assert result.accepted is True
    assert result.metadata["engine"] == "rizzoflow"


def test_decide_null_choice_falls_back_to_argmax(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _choice_payload(
        {"decision": _choice_answer(None, {"retry": 0.6, "abort": 0.4})}
    )
    monkeypatch.setattr(
        "jev_cpu_agentbridge.engine.rizzoflow.urllib.request.urlopen",
        lambda request, timeout=None: _FakeResponse(payload),
    )
    engine = RizzoFlowEngine(base_url="http://localhost:8017", min_selected_probability=0.5)

    result = engine.decide(
        state="test",
        question="which?",
        options=[Option(id="retry", description="Retry"), Option(id="abort", description="Abort")],
    )

    assert result.decision.id == "retry"


def test_decide_batch_maps_each_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _choice_payload(
        {
            "0": _choice_answer("retry", {"retry": 0.9, "abort": 0.1}),
            "1": _choice_answer("no", {"yes": 0.2, "no": 0.8}),
        }
    )
    monkeypatch.setattr(
        "jev_cpu_agentbridge.engine.rizzoflow.urllib.request.urlopen",
        lambda request, timeout=None: _FakeResponse(payload),
    )
    engine = RizzoFlowEngine(base_url="http://localhost:8017", min_selected_probability=0.5)

    results = engine.decide_batch(
        state="test",
        decisions=[
            (
                "which?",
                [Option(id="retry", description="Retry"), Option(id="abort", description="Abort")],
            ),
            ("notify?", [Option(id="yes", description="Yes"), Option(id="no", description="No")]),
        ],
    )

    assert [r.decision.id for r in results] == ["retry", "no"]


def test_decide_batch_empty_returns_empty_list() -> None:
    engine = RizzoFlowEngine(base_url="http://localhost:8017", min_selected_probability=0.5)
    assert engine.decide_batch(state="test", decisions=[]) == []


def test_rejects_option_count_out_of_range() -> None:
    engine = RizzoFlowEngine(base_url="http://localhost:8017", min_selected_probability=0.5)
    with pytest.raises(ValueError):
        engine.decide(state="test", question="which?", options=[Option(id="a", description="A")])
