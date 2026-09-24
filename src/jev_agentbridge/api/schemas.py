"""The public REST contract (v1). Identical for every engine.

FastAPI publishes it as OpenAPI at `/openapi.json` (interactive docs at `/docs`).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..core.models import MAX_OPTIONS, MIN_OPTIONS

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


class DecideRequest(BaseModel):
    """Single decision."""

    model_config = ConfigDict(populate_by_name=True)

    state: str | dict[str, Any] | list[Any]
    question: str = Field(alias="criterion")
    options: list[OptionIn] = Field(min_length=MIN_OPTIONS, max_length=MAX_OPTIONS)
    min_selected_probability: float | None = Threshold


class BatchDecideItem(BaseModel):
    """One decision within a batch; shares the top-level state."""

    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(alias="criterion")
    options: list[OptionIn] = Field(min_length=MIN_OPTIONS, max_length=MAX_OPTIONS)
    min_selected_probability: float | None = Threshold


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
    decision: OptionIn
    probabilities: dict[str, float] = Field(description="One probability per option id.")
    selected_probability: float
    accepted: bool = Field(description="selected_probability >= threshold")
    threshold: float
    metadata: dict[str, Any] = Field(
        description="engine, model, model_revision, mode, latency_ms, input_tokens?, "
        "engine_details? (adapter-specific)."
    )


class BatchDecideResponse(BaseModel):
    decisions: list[DecideResponse]


class EngineInfoOut(BaseModel):
    name: str
    model: str
    revision: str
    native_batch: bool


class InfoResponse(BaseModel):
    api_version: str
    version: str
    engine: EngineInfoOut
    available_engines: list[str]
    min_options: int
    max_options: int
    default_min_selected_probability: float
    supported_modes: list[str]


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
