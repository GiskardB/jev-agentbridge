"""RizzoFlow decision engine adapter (optional backend, JEV_ENGINE=rizzoflow).

RizzoFlow (https://github.com/Rizzo-AI-Academy/rizzo-flow) runs its own llama.cpp-backed HTTP
server; this engine is a thin client for its native `POST /v1/decisions` endpoint. It has no
extra Python dependency (stdlib urllib only) — the model itself runs in RizzoFlow's own process,
started separately with `rizzo serve` (see their README), not inside this Bridge.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Sequence

from .base import DecisionEngine, DecisionResult, Option


class RizzoFlowEngine(DecisionEngine):
    """Decision engine backed by a running RizzoFlow server (POST /v1/decisions)."""

    def __init__(self, *, base_url: str, min_selected_probability: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._min_selected_probability = min_selected_probability

    @staticmethod
    def _question(question: str, options: Sequence[Option]) -> dict[str, Any]:
        if not 2 <= len(options) <= 16:
            raise ValueError("A decision must contain between 2 and 16 options.")
        return {
            "type": "choice",
            "instructions": question,
            # Without this, RizzoFlow's default policy lets the model abstain
            # ("cannot determine"); we always want a concrete decision, same as
            # the other engines — `accepted` already carries the confidence signal.
            "policy": {"allow_abstain": False},
            "options": [{"id": option.id, "description": option.description} for option in options],
        }

    def _post(self, state: Any, questions: dict[str, Any], mode: str) -> dict[str, Any]:
        body = json.dumps({"state": state, "questions": questions, "mode": mode}).encode()
        request = urllib.request.Request(
            f"{self._base_url}/v1/decisions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read())
        except urllib.error.URLError as error:
            raise RuntimeError(f"RizzoFlow request failed: {error}") from error

    @staticmethod
    def _result_from_answer(
        answer: dict[str, Any],
        options: Sequence[Option],
        threshold: float,
        elapsed_ms: float,
    ) -> DecisionResult:
        probabilities = {k: v for k, v in answer["probabilities"].items() if not k.startswith("__")}
        selected_id = answer["choice"] or max(probabilities, key=probabilities.get)
        decision = next(option for option in options if option.id == selected_id)
        selected_probability = probabilities[selected_id]
        return DecisionResult(
            decision=decision,
            probabilities=probabilities,
            selected_probability=selected_probability,
            accepted=selected_probability >= threshold,
            metadata={
                "engine": "rizzoflow",
                "mode": "direct",
                "status": answer["status"],
                "latency_ms": round(elapsed_ms, 3),
            },
        )

    def decide(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: Sequence[Option],
        min_selected_probability: float | None = None,
    ) -> DecisionResult:
        """Evaluate one decision."""

        threshold = (
            self._min_selected_probability
            if min_selected_probability is None
            else min_selected_probability
        )
        started = time.perf_counter()
        result = self._post(state, {"decision": self._question(question, options)}, mode="direct")
        elapsed_ms = (time.perf_counter() - started) * 1000
        return self._result_from_answer(
            result["answers"]["decision"], options, threshold, elapsed_ms
        )

    def decide_batch(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        decisions: Sequence[tuple[str, Sequence[Option]]],
        min_selected_probability: float | None = None,
    ) -> list[DecisionResult]:
        """Evaluate decisions sharing one state in a single RizzoFlow call (mode=shared)."""

        if not decisions:
            return []

        threshold = (
            self._min_selected_probability
            if min_selected_probability is None
            else min_selected_probability
        )
        questions = {
            str(index): self._question(q, opts) for index, (q, opts) in enumerate(decisions)
        }
        started = time.perf_counter()
        result = self._post(state, questions, mode="shared")
        elapsed_ms = (time.perf_counter() - started) * 1000
        return [
            self._result_from_answer(result["answers"][str(index)], opts, threshold, elapsed_ms)
            for index, (_, opts) in enumerate(decisions)
        ]
