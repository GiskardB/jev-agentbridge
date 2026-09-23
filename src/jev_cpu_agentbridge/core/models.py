"""Engine-agnostic domain models: the shape every decision has, whatever scores it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union

State = Union[str, dict[str, Any], list[Any]]

MIN_OPTIONS = 2
MAX_OPTIONS = 16


@dataclass(frozen=True)
class Option:
    """One candidate outcome of a decision."""

    id: str
    description: str


@dataclass(frozen=True)
class Decision:
    """A closed choice to evaluate: a criterion plus 2-16 options."""

    question: str
    options: tuple[Option, ...]
    min_selected_probability: float | None = None


@dataclass(frozen=True)
class Scores:
    """What an adapter returns: a probability per option id, nothing else decided.

    `details` carries adapter-specific diagnostics (prompt hash, token counts, backend
    status...) and is surfaced under `metadata.engine_details` without interpretation.
    """

    probabilities: dict[str, float]
    input_tokens: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionResult:
    """The standard outcome returned by the service for every engine."""

    decision: Option
    probabilities: dict[str, float]
    selected_probability: float
    accepted: bool
    threshold: float
    metadata: dict[str, Any] = field(default_factory=dict)
