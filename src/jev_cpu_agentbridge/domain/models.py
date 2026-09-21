"""Domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Option(BaseModel):
    """A decision option."""

    id: str
    description: str

    model_config = {"populate_by_name": True}


class DecisionRequest(BaseModel):
    """Canonical decision request."""

    state: str | dict | list
    question: str = Field(alias="criterion")
    options: list[Option] = Field(min_length=2, max_length=16)

    model_config = {"populate_by_name": True}


class DecisionResponse(BaseModel):
    """Canonical decision response."""

    decision: Option
    probabilities: dict[str, float]
    selected_probability: float
    accepted: bool
    metadata: dict


class BatchDecisionRequest(BaseModel):
    """Batch decision request sharing one state."""

    state: str | dict | list
    decisions: list[DecisionRequest]


class BatchDecisionResponse(BaseModel):
    """Batch decision response."""

    decisions: list[DecisionResponse]


class InfoResponse(BaseModel):
    """Engine information."""

    engine: str
    model: str
    revision: str
    supported_modes: list[str]
    max_options: int
    version: str


class ErrorResponse(BaseModel):
    """Structured error response."""

    error: dict[str, str]


class HealthResponse(BaseModel):
    """Health status."""

    status: str


class ReadyResponse(BaseModel):
    """Readiness status."""

    status: str
    model: str
