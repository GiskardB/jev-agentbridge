"""Laya decision engine adapter (optional backend, selected via JEV_ENGINE=laya).

Laya scores all options for a question in one non-autoregressive forward pass over an
encoder model, instead of the next-token-logit scoring SemIfEngine does on a causal LM.
See https://github.com/NandhaKishorM/laya.
"""

from __future__ import annotations

import time
from typing import Any, Sequence

from .base import DecisionEngine, DecisionResult, Option


class LayaEngine(DecisionEngine):
    """Decision engine backed by the Laya package.

    Requires the optional `laya` dependency: `pip install jev-cpu-agentbridge[laya]`.
    """

    def __init__(
        self,
        *,
        model_name: str,
        subfolder: str | None,
        device: str,
        min_selected_probability: float,
    ) -> None:
        try:
            import laya
        except ImportError as error:
            raise RuntimeError(
                "JEV_ENGINE=laya requires the 'laya' package. Install it with "
                "`pip install jev-cpu-agentbridge[laya]`."
            ) from error

        self._agent = laya.load(model_name, device=device, subfolder=subfolder)
        self._model_name = model_name
        self._min_selected_probability = min_selected_probability

    @staticmethod
    def _question(question: str, options: Sequence[Option]) -> dict[str, Any]:
        if not 2 <= len(options) <= 16:
            raise ValueError("A decision must contain between 2 and 16 options.")
        return {
            "type": "choice",
            "instructions": question,
            "criteria": {option.id: option.description for option in options},
        }

    def _result_from_answer(
        self,
        answer: dict[str, Any],
        options: Sequence[Option],
        threshold: float,
        started: float,
    ) -> DecisionResult:
        selected_id = answer["choice"]
        decision = next(option for option in options if option.id == selected_id)
        selected_probability = float(answer["confidence"])
        elapsed_ms = (time.perf_counter() - started) * 1000
        return DecisionResult(
            decision=decision,
            probabilities=dict(answer["probabilities"]),
            selected_probability=selected_probability,
            accepted=selected_probability >= threshold,
            metadata={
                "engine": "laya",
                "mode": "direct",
                "model": self._model_name,
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
        result = self._agent.predict(state, {"decision": self._question(question, options)})
        return self._result_from_answer(result["answers"]["decision"], options, threshold, started)

    def decide_batch(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        decisions: Sequence[tuple[str, Sequence[Option]]],
        min_selected_probability: float | None = None,
    ) -> list[DecisionResult]:
        """Evaluate decisions sharing one state in a single forward pass."""

        if not decisions:
            return []

        threshold = (
            self._min_selected_probability
            if min_selected_probability is None
            else min_selected_probability
        )
        started = time.perf_counter()
        questions = {
            str(index): self._question(question, options)
            for index, (question, options) in enumerate(decisions)
        }
        result = self._agent.predict(state, questions)
        return [
            self._result_from_answer(result["answers"][str(index)], options, threshold, started)
            for index, (_, options) in enumerate(decisions)
        ]
