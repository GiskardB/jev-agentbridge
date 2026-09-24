"""The public REST contract (v1). Identical for every engine.

FastAPI publishes it as OpenAPI at `/openapi.json` (interactive docs at `/docs`).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.models import MAX_OPTIONS, MIN_OPTIONS, QuestionType

Threshold = Field(
    default=None,
    ge=0.0,
    le=1.0,
    description="Acceptance threshold for this decision; defaults to the service's "
    "JEV_MIN_SELECTED_PROBABILITY.",
)


class OptionIn(BaseModel):
    id: str = Field(min_length=1)
    description: str


class DecisionIn(BaseModel):
    """The question part of a decision, for every type."""

    model_config = ConfigDict(populate_by_name=True)

    type: QuestionType = Field(
        default="choice",
        description="choice: pick one option. noul: yes/no, no options. "
        "score: options are the levels of an ordinal scale, lowest first.",
    )
    question: str = Field(alias="criterion")
    options: list[OptionIn] | None = Field(
        default=None,
        min_length=MIN_OPTIONS,
        max_length=MAX_OPTIONS,
        description="Required for choice and score (levels, lowest first); omitted for noul.",
    )
    yes_description: str | None = Field(
        default=None, description="noul only: what 'yes' means, when not obvious."
    )
    no_description: str | None = Field(
        default=None, description="noul only: what 'no' means, when not obvious."
    )
    min_selected_probability: float | None = Threshold

    @model_validator(mode="after")
    def _fields_match_type(self) -> "DecisionIn":
        if self.type == "noul":
            if self.options is not None:
                raise ValueError("a noul decision takes no options (its answers are yes/no)")
        else:
            if self.options is None:
                raise ValueError(f"a {self.type} decision needs options")
            if self.yes_description is not None or self.no_description is not None:
                raise ValueError("yes_description/no_description apply to noul decisions only")
        return self


class DecideRequest(DecisionIn):
    """Single decision."""

    state: str | dict[str, Any] | list[Any]


class BatchDecideItem(DecisionIn):
    """One decision within a batch; shares the top-level state. Types can be mixed."""


class BatchDecideRequest(BaseModel):
    """Several decisions sharing one state."""

    state: str | dict[str, Any] | list[Any]
    decisions: list[BatchDecideItem] = Field(min_length=1)
    min_selected_probability: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Default threshold for every decision in the batch that sets none.",
    )


class DecideResponse(BaseModel):
    type: QuestionType
    decision: OptionIn = Field(
        description="The most likely option; for noul `yes` or `no`, for score the level."
    )
    probabilities: dict[str, float] = Field(
        description="One probability per option id (noul: `yes` and `no`)."
    )
    selected_probability: float
    accepted: bool = Field(description="selected_probability >= threshold")
    threshold: float
    score: float | None = Field(
        default=None,
        description="score only: expected level, 0 (first level) to len(options) - 1.",
    )
    noul: float | None = Field(default=None, description="noul only: probability of yes.")
    metadata: dict[str, Any] = Field(
        description="engine, model, model_revision, mode, latency_ms, native_type, "
        "input_tokens?, engine_details? (adapter-specific)."
    )


class BatchDecideResponse(BaseModel):
    decisions: list[DecideResponse]


class EngineInfoOut(BaseModel):
    name: str
    model: str
    revision: str
    native_batch: bool
    native_types: list[str] = Field(
        description="Question types scored natively; the others are emulated as a choice."
    )


class InfoResponse(BaseModel):
    api_version: str
    version: str
    engine: EngineInfoOut
    available_engines: list[str]
    min_options: int
    max_options: int
    default_min_selected_probability: float
    supported_modes: list[str]
    supported_types: list[str]


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    engine: str
    model: str


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody
