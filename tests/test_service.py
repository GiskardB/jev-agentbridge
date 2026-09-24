"""Tests for DecisionService: the policy shared by every engine."""

from __future__ import annotations

import pytest

from jev_agentbridge.core.errors import (
    DuplicateOptionIdError,
    EngineError,
    EngineNotReadyError,
    InvalidDecisionError,
    OptionCountError,
)
from jev_agentbridge.core.models import Decision, Option, Scores
from jev_agentbridge.core.service import DecisionService
from tests.conftest import FakeAdapter

TWO = (Option("a", "A"), Option("b", "B"))


def test_default_and_per_decision_threshold() -> None:
    service = DecisionService(FakeAdapter(top=0.7), default_threshold=0.6)
    default = service.decide(state="s", decision=Decision("q", TWO))
    assert default.accepted is True and default.threshold == 0.6
    strict = service.decide(state="s", decision=Decision("q", TWO, min_selected_probability=0.9))
    assert strict.accepted is False and strict.threshold == 0.9


def test_standard_metadata() -> None:
    result = DecisionService(FakeAdapter(), default_threshold=0.5).decide(
        state="s", decision=Decision("q", TWO)
    )
    assert result.decision.id == "a"
    assert result.metadata["engine"] == "fake"
    assert result.metadata["mode"] == "direct"
    assert result.metadata["input_tokens"] == 7
    assert result.metadata["engine_details"] == {"k": "v"}
    assert "latency_ms" in result.metadata


@pytest.mark.parametrize(
    "options, error",
    [
        ((Option("a", "A"),), OptionCountError),
        (tuple(Option(str(i), str(i)) for i in range(17)), OptionCountError),
        ((Option("a", "A"), Option("a", "B")), DuplicateOptionIdError),
    ],
)
def test_invalid_decisions(options, error) -> None:
    with pytest.raises(error):
        DecisionService(FakeAdapter(), default_threshold=0.5).decide(
            state="s", decision=Decision("q", options)
        )


def test_invalid_threshold() -> None:
    with pytest.raises(InvalidDecisionError):
        DecisionService(FakeAdapter(), default_threshold=0.5).decide(
            state="s", decision=Decision("q", TWO, min_selected_probability=1.5)
        )


def test_not_ready() -> None:
    with pytest.raises(EngineNotReadyError):
        DecisionService(FakeAdapter(ready=False), default_threshold=0.5).decide(
            state="s", decision=Decision("q", TWO)
        )


def test_adapter_exception_becomes_engine_error() -> None:
    adapter = FakeAdapter()
    adapter.error = KeyError("boom")
    with pytest.raises(EngineError):
        DecisionService(adapter, default_threshold=0.5).decide(
            state="s", decision=Decision("q", TWO)
        )


def test_missing_option_probability_is_engine_error() -> None:
    class Partial(FakeAdapter):
        def score(self, *, state, decision):
            return Scores(probabilities={"a": 1.0})

    with pytest.raises(EngineError, match="no probability"):
        DecisionService(Partial(), default_threshold=0.5).decide(
            state="s", decision=Decision("q", TWO)
        )


def test_batch_mode_and_per_item_threshold() -> None:
    adapter = FakeAdapter(top=0.7, thread_safe=False)
    results = DecisionService(adapter, default_threshold=0.5).decide_batch(
        state="s",
        decisions=[Decision("q1", TWO), Decision("q2", TWO, min_selected_probability=0.8)],
    )
    assert [r.accepted for r in results] == [True, False]
    assert all(r.metadata["mode"] == "shared" for r in results)
    assert adapter.batch_calls == 1


def test_empty_batch() -> None:
    assert DecisionService(FakeAdapter(), default_threshold=0.5).decide_batch(
        state="s", decisions=[]
    ) == []
