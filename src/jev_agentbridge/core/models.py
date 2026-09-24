"""Engine-agnostic domain models: the shape every decision has, whatever scores it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Union

State = Union[str, dict[str, Any], list[Any]]

MIN_OPTIONS = 2
MAX_OPTIONS = 16

# The three JEV question types.
#   choice: pick one category out of 2-16 options.
#   noul:   yes/no; the options are always `yes` then `no`.
#   score:  place the state on an ordinal scale; the options are the levels, lowest first.
QuestionType = Literal["choice", "noul", "score"]
QUESTION_TYPES: tuple[QuestionType, ...] = ("choice", "noul", "score")

YES_ID = "yes"
NO_ID = "no"
DEFAULT_YES_DESCRIPTION = "Yes"
DEFAULT_NO_DESCRIPTION = "No"


@dataclass(frozen=True)
class Option:
    """One candidate outcome of a decision."""

    id: str
    description: str


@dataclass(frozen=True)
class Decision:
    """A closed question to evaluate: a criterion, its type and 2-16 options.

    Every type is carried as options, so adapters and the service handle one shape: a noul
    decision has the options `yes` and `no` (see `Decision.noul`), a score decision has its
    levels as options, lowest first.
    """

    question: str
    options: tuple[Option, ...]
    min_selected_probability: float | None = None
    type: QuestionType = "choice"

    @classmethod
    def noul(
        cls,
        question: str,
        *,
        yes_description: str | None = None,
        no_description: str | None = None,
        min_selected_probability: float | None = None,
    ) -> "Decision":
        """A yes/no decision; the descriptions say what "yes" and "no" mean, if not obvious."""

        return cls(
            question=question,
            options=(
                Option(YES_ID, yes_description or DEFAULT_YES_DESCRIPTION),
                Option(NO_ID, no_description or DEFAULT_NO_DESCRIPTION),
            ),
            min_selected_probability=min_selected_probability,
            type="noul",
        )

    def custom_noul_descriptions(self) -> dict[str, str] | None:
        """For a noul decision, `{"yes": ..., "no": ...}` if either description was given."""

        yes, no = self.options[0].description, self.options[1].description
        if (yes, no) == (DEFAULT_YES_DESCRIPTION, DEFAULT_NO_DESCRIPTION):
            return None
        return {YES_ID: yes, NO_ID: no}


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
    type: QuestionType = "choice"
    # score decisions: expected level, 0 (first level) to len(options) - 1.
    score: float | None = None
    # noul decisions: probability of "yes".
    noul: float | None = None
