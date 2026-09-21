"""FastAPI request/response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OptionIn(BaseModel):
    id: str
    description: str

    model_config = {"populate_by_name": True}


class DecideRequest(BaseModel):
    state: str | dict | list
    question: str = Field(alias="criterion")
    options: list[OptionIn] = Field(min_length=2, max_length=16)

    model_config = {"populate_by_name": True}


class BatchDecideRequest(BaseModel):
    state: str | dict | list
    decisions: list[DecideRequest]


class DecideResponse(BaseModel):
    decision: dict[str, str]
    probabilities: dict[str, float]
    selected_probability: float
    accepted: bool
    metadata: dict[str, Any]


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
