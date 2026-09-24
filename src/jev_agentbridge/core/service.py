"""DecisionService: the engine-agnostic half of every decision.

The service validates the decision, delegates scoring to the configured adapter, then
applies the same policy for every engine: argmax over option ids, the acceptance
threshold (per-request override or service default), timing and the metadata envelope.

Question types (choice, noul, score) the adapter does not score natively are emulated as a
choice over the same options; the score's expected level is computed here, so it means the
same thing for every engine.
"""

from __future__ import annotations

import contextlib
import dataclasses
import threading
import time
from typing import Any, Iterable, Sequence

from .errors import (
    DecisionError,
    DuplicateOptionIdError,
    EngineError,
    EngineNotReadyError,
    InvalidDecisionError,
    OptionCountError,
)
from .models import (
    MAX_OPTIONS,
    MIN_OPTIONS,
    NO_ID,
    QUESTION_TYPES,
    YES_ID,
    Decision,
    DecisionResult,
    Scores,
    State,
)
from .ports import DecisionAdapter, EngineInfo


class DecisionService:
    """Runs decisions against one adapter with a uniform policy."""

    def __init__(
        self,
        adapter: DecisionAdapter,
        *,
        default_threshold: float,
        native_types: bool | Iterable[str] = True,
    ) -> None:
        _check_threshold(default_threshold)
        self._adapter = adapter
        self._default_threshold = default_threshold
        # True: every type the adapter supports goes native. False: everything is asked as a
        # choice. A set: only those types go native (when the adapter supports them).
        self._native_types = (
            native_types if isinstance(native_types, bool) else frozenset(native_types)
        )
        # Adapters that are not thread-safe are serialized here, so the API can run
        # requests in a thread pool without every adapter re-implementing locking.
        self._lock = (
            contextlib.nullcontext() if adapter.info().thread_safe else threading.Lock()
        )

    @property
    def default_threshold(self) -> float:
        return self._default_threshold

    def info(self) -> EngineInfo:
        return self._adapter.info()

    def native_types(self) -> frozenset[str]:
        """Question types scored natively by the engine (the rest are emulated)."""

        supported = frozenset(self._adapter.info().native_types)
        if self._native_types is False:
            supported = frozenset()
        elif self._native_types is not True:
            supported &= self._native_types
        return supported | {"choice"}

    def is_ready(self) -> bool:
        try:
            return bool(self._adapter.is_ready())
        except Exception:  # noqa: BLE001 - readiness must never raise
            return False

    def decide(self, *, state: State, decision: Decision) -> DecisionResult:
        """Evaluate one decision."""

        _validate(decision)
        self._ensure_ready()
        started = time.perf_counter()
        native = self.native_types()
        with self._lock:
            scores = self._call(
                self._adapter.score, state=state, decision=_as_scored(decision, native)
            )
        latency_ms = (time.perf_counter() - started) * 1000
        return self._to_result(
            decision, scores, mode="direct", latency_ms=latency_ms, native=native
        )

    def decide_batch(
        self, *, state: State, decisions: Sequence[Decision]
    ) -> list[DecisionResult]:
        """Evaluate several decisions sharing one state.

        `latency_ms` on each result is the wall time of the whole batch.
        """

        if not decisions:
            return []
        for decision in decisions:
            _validate(decision)
        self._ensure_ready()
        started = time.perf_counter()
        native = self.native_types()
        scored = [_as_scored(decision, native) for decision in decisions]
        with self._lock:
            scores = self._call(self._adapter.score_batch, state=state, decisions=scored)
        latency_ms = (time.perf_counter() - started) * 1000
        if len(scores) != len(decisions):
            raise EngineError(
                f"Adapter returned {len(scores)} results for {len(decisions)} decisions"
            )
        return [
            self._to_result(
                decision, score, mode="shared", latency_ms=latency_ms, native=native
            )
            for decision, score in zip(decisions, scores)
        ]

    def _ensure_ready(self) -> None:
        if not self.is_ready():
            raise EngineNotReadyError("The decision engine is not ready yet")

    @staticmethod
    def _call(method: Any, **kwargs: Any) -> Any:
        try:
            return method(**kwargs)
        except DecisionError:
            raise
        except Exception as error:  # noqa: BLE001 - anything else is an engine fault
            raise EngineError(f"{type(error).__name__}: {error}") from error

    def _to_result(
        self,
        decision: Decision,
        scores: Scores,
        *,
        mode: str,
        latency_ms: float,
        native: frozenset[str],
    ) -> DecisionResult:
        probabilities = _option_probabilities(decision, scores)
        selected = max(decision.options, key=lambda option: probabilities[option.id])
        selected_probability = probabilities[selected.id]
        threshold = (
            self._default_threshold
            if decision.min_selected_probability is None
            else decision.min_selected_probability
        )
        info = self._adapter.info()
        metadata: dict[str, Any] = {
            "engine": info.name,
            "model": info.model,
            "model_revision": info.revision,
            "mode": mode,
            "latency_ms": round(latency_ms, 3),
            "native_type": decision.type in native,
        }
        if scores.input_tokens is not None:
            metadata["input_tokens"] = scores.input_tokens
        if scores.details:
            metadata["engine_details"] = dict(scores.details)
        return DecisionResult(
            decision=selected,
            probabilities=probabilities,
            selected_probability=selected_probability,
            accepted=selected_probability >= threshold,
            threshold=threshold,
            metadata=metadata,
            type=decision.type,
            score=_expected_level(decision, probabilities) if decision.type == "score" else None,
            noul=probabilities[YES_ID] if decision.type == "noul" else None,
        )


def _as_scored(decision: Decision, native: frozenset[str]) -> Decision:
    """The decision as the adapter sees it: unchanged if native, otherwise a plain choice."""

    if decision.type in native:
        return decision
    return dataclasses.replace(decision, type="choice")


def _expected_level(decision: Decision, probabilities: dict[str, float]) -> float:
    """Expected level of a score decision: 0 for the first level, len(options) - 1 for the last."""

    total = sum(probabilities.values()) or 1.0
    expected = sum(
        index * probabilities[option.id] for index, option in enumerate(decision.options)
    )
    return round(expected / total, 4)


def _check_threshold(value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise InvalidDecisionError(
            f"min_selected_probability must be between 0 and 1, got {value}"
        )


def _validate(decision: Decision) -> None:
    if decision.type not in QUESTION_TYPES:
        raise InvalidDecisionError(
            f"Unknown question type {decision.type!r}; expected one of {list(QUESTION_TYPES)}"
        )
    if decision.type == "noul" and [o.id for o in decision.options] != [YES_ID, NO_ID]:
        raise InvalidDecisionError("A noul decision has exactly the options 'yes' and 'no'")
    count = len(decision.options)
    if not MIN_OPTIONS <= count <= MAX_OPTIONS:
        raise OptionCountError(
            f"A decision must contain between {MIN_OPTIONS} and {MAX_OPTIONS} options, "
            f"got {count}"
        )
    ids = [option.id for option in decision.options]
    duplicates = sorted({option_id for option_id in ids if ids.count(option_id) > 1})
    if duplicates:
        raise DuplicateOptionIdError(f"Option ids must be unique; duplicated: {duplicates}")
    if decision.min_selected_probability is not None:
        _check_threshold(decision.min_selected_probability)


def _option_probabilities(decision: Decision, scores: Scores) -> dict[str, float]:
    """Keep exactly one probability per option id, in option order."""

    missing = [o.id for o in decision.options if o.id not in scores.probabilities]
    if missing:
        raise EngineError(f"Adapter returned no probability for options {missing}")
    return {o.id: float(scores.probabilities[o.id]) for o in decision.options}
