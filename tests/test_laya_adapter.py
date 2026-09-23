"""Tests for the Laya adapter with a fake Laya agent (no model download)."""

from __future__ import annotations

from jev_cpu_agentbridge.adapters.laya.adapter import LayaAdapter
from jev_cpu_agentbridge.core.models import Decision, Option
from jev_cpu_agentbridge.core.service import DecisionService


class _FakeAgent:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def predict(self, state, questions):
        self.calls.append(questions)
        answers = {}
        for key, question in questions.items():
            ids = list(question["criteria"])
            answers[key] = {
                "choice": ids[-1],
                "confidence": 0.7,
                "probabilities": {i: (0.7 if i == ids[-1] else 0.3 / (len(ids) - 1)) for i in ids},
            }
        return {"answers": answers}


def test_score_and_batch_in_one_forward_pass() -> None:
    agent = _FakeAgent()
    adapter = LayaAdapter(agent=agent, model_name="laya", subfolder=None)
    service = DecisionService(adapter, default_threshold=0.6)
    decisions = [
        Decision("a?", (Option("x", "X"), Option("y", "Y"))),
        Decision("b?", (Option("p", "P"), Option("q", "Q"), Option("r", "R"))),
    ]
    results = service.decide_batch(state="s", decisions=decisions)
    assert [r.decision.id for r in results] == ["y", "r"]
    assert all(r.accepted for r in results)
    assert len(agent.calls) == 1
    assert adapter.info().thread_safe is False
