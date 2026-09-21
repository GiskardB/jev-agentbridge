"""Core decision engine interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence


@dataclass(frozen=True)
class Option:
    """A decision option."""

    id: str
    description: str


@dataclass(frozen=True)
class DecisionResult:
    """Result of a decision evaluation."""

    decision: Option
    probabilities: dict[str, float]
    selected_probability: float
    accepted: bool
    metadata: dict[str, Any] = field(default_factory=dict)


class DecisionEngine(Protocol):
    """Protocol implemented by decision engines."""

    def decide(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: Sequence[Option],
        min_selected_probability: float,
    ) -> DecisionResult:
        """Evaluate a single decision."""

    def decide_batch(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        decisions: Sequence[tuple[str, Sequence[Option]]],
        min_selected_probability: float,
    ) -> list[DecisionResult]:
        """Evaluate multiple decisions sharing the same state."""
