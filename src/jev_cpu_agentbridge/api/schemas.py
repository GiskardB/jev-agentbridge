"""FastAPI request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OptionIn(BaseModel):
    id: str
    description: str


class DecideRequest(BaseModel):
    """Single decision request."""

    state: str | dict | list
    question: str = Field(alias="criterion")
    options: list[OptionIn] = Field(min_length=2, max_length=16)

    model_config = {"populate_by_name": True}


class BatchDecideItem(BaseModel):
    """A single decision within a batch — shares the top-level state."""

    question: str = Field(alias="criterion")
    options: list[OptionIn] = Field(min_length=2, max_length=16)

    model_config = {"populate_by_name": True}


class BatchDecideRequest(BaseModel):
    """Batch decision request sharing one state."""

    state: str | dict | list
    decisions: list[BatchDecideItem] = Field(min_length=1)


class DecideResponse(BaseModel):
    decision: dict[str, str]
    probabilities: dict[str, float]
    selected_probability: float
    accepted: bool
    metadata: dict


class BatchDecideResponse(BaseModel):
    decisions: list[DecideResponse]


class InfoResponse(BaseModel):
    engine: str
    model: str
    revision: str
    supported_modes: list[str]
    max_options: int
    version: str


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    model: str
