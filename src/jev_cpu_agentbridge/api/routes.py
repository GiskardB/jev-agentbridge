"""FastAPI route definitions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing import Callable, Any

from ..engine.base import DecisionResult, DecisionEngine
from ..runtime.settings import Settings
from .errors import BridgeError, ErrorCode
from .schemas import (
    BatchDecideRequest,
    BatchDecideResponse,
    DecideRequest,
    DecideResponse,
    HealthResponse,
    InfoResponse,
    ReadyResponse,
)


def create_router(
    get_engine: Callable[[], DecisionEngine],
    settings: Settings,
) -> APIRouter:
    """Create the API router."""

    router = APIRouter()

    @router.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @router.get("/ready", response_model=ReadyResponse)
    async def ready() -> ReadyResponse:
        try:
            engine = get_engine()
            if not getattr(engine, "_ready", False):
                raise HTTPException(status_code=503, detail={"status": "not ready"})
        except (RuntimeError, LookupError):
            raise HTTPException(status_code=503, detail={"status": "not ready"})
        return ReadyResponse(
            status="ready",
            model=settings.model_name,
        )

    @router.get("/v1/info", response_model=InfoResponse)
    async def info() -> InfoResponse:
        return InfoResponse(
            engine="semif",
            model=settings.model_name,
            revision=settings.model_revision,
            supported_modes=["direct", "shared"],
            max_options=16,
            version="0.1.0",
        )

    @router.post("/v1/decide", response_model=DecideResponse)
    async def decide(request: DecideRequest) -> DecideResponse:
        engine = get_engine()
        try:
            result: DecisionResult = engine.decide(
                state=request.state,
                question=request.question,
                options=_to_domain_options(request.options),
                min_selected_probability=request.model_dump().get(
                    "min_selected_probability"
                ),
            )
        except BridgeError as error:
            raise HTTPException(
                status_code=400, detail=error.to_response()
            )
        except Exception as error:  # noqa: BLE001
            raise HTTPException(
                status_code=500,
                detail={"code": ErrorCode.ENGINE_ERROR, "message": str(error)},
            )
        return _to_response(result)

    @router.post("/v1/decide/batch", response_model=BatchDecideResponse)
    async def decide_batch(request: BatchDecideRequest) -> BatchDecideResponse:
        try:
            engine = get_engine()
        except RuntimeError:
            raise HTTPException(status_code=503, detail={"status": "not ready"})
        try:
            decisions: list[tuple[str, list]] = [
                (dec.question, _to_domain_options(dec.options))
                for dec in request.decisions
            ]
            results: list[DecisionResult] = engine.decide_batch(
                state=request.state,
                decisions=decisions,
                min_selected_probability=None,
            )
        except BridgeError as error:
            raise HTTPException(
                status_code=400, detail=error.to_response()
            )
        except Exception as error:  # noqa: BLE001
            raise HTTPException(
                status_code=500,
                detail={"code": ErrorCode.ENGINE_ERROR, "message": str(error)},
            )
        return BatchDecideResponse(decisions=[_to_response(r) for r in results])

    return router


def _to_domain_options(options: list[dict]) -> list:
    from ..engine.base import Option

    return [Option(id=o["id"], description=o["description"]) for o in options]


def _to_response(result: DecisionResult) -> dict:
    return DecideResponse(
        decision={"id": result.decision.id, "description": result.decision.description},
        probabilities=result.probabilities,
        selected_probability=result.selected_probability,
        accepted=result.accepted,
        metadata=result.metadata,
    ).model_dump()