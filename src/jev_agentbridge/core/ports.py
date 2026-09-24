"""The port every decision backend implements.

An adapter only *scores*: given a state and a decision it returns one probability per
option id. Validation, argmax, the acceptance threshold, timing and the response shape
are owned by `DecisionService`, so they behave identically for every engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

from .models import Decision, QuestionType, Scores, State


@dataclass(frozen=True)
class EngineInfo:
    """Static description of an adapter, reported by `GET /v1/info`."""

    name: str
    model: str
    revision: str = "n/a"
    # True when score_batch() is cheaper than N score() calls (shared prefix, one request...).
    native_batch: bool = False
    # False makes the service serialize calls to this adapter behind a lock.
    thread_safe: bool = False
    # Question types the engine scores natively. The service emulates the others as a
    # choice over the same options (noul: yes/no, score: the levels).
    native_types: frozenset[QuestionType] = frozenset({"choice"})


@runtime_checkable
class DecisionAdapter(Protocol):
    """Protocol implemented by every engine adapter (semif, laya, rizzoflow, ...)."""

    def info(self) -> EngineInfo:
        """Describe the adapter and its model."""

    def is_ready(self) -> bool:
        """True once the adapter can serve score() calls."""

    def score(self, *, state: State, decision: Decision) -> Scores:
        """Return a probability per option id for one decision.

        `decision.type` is always one of `info().native_types`: noul answers are keyed
        `yes`/`no`, score answers by the level option ids.
        """

    def score_batch(self, *, state: State, decisions: Sequence[Decision]) -> list[Scores]:
        """Score several decisions sharing one state; same order as `decisions`.

        Adapters without a cheaper shared path can simply loop over score().
        """
