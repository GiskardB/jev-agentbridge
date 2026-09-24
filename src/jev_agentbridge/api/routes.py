"""HTTP routes: map the v1 contract to DecisionService calls, nothing engine-specific.

Handlers are plain `def`, so FastAPI runs them in its thread pool: a slow CPU decision
no longer blocks the event loop (and with it /health, /ready and other requests).
"""

from __future__ import annotations

from typing import Callable

from fastapi import APIRouter

from .. import API_VERSION, __version__
from ..adapters.registry import available_engines
from ..core.errors import EngineNotReadyError
from ..core.models import MAX_OPTIONS, MIN_OPTIONS, Decision, DecisionResult, Option
from ..core.service import DecisionService
from .errors import error_response
from .schemas import (
    BatchDecideItem,
    BatchDecideRequest,
    BatchDecideResponse,
    DecideRequest,
    DecideResponse,
    EngineInfoOut,
    ErrorResponse,
    HealthResponse,
    InfoResponse,
    OptionIn,
    ReadyResponse,
)

ServiceProvider = Callable[[], "DecisionService | None"]

_ERRORS = {
    400: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def create_router(get_service: ServiceProvider) -> APIRouter:
    router = APIRouter()

    def service() -> DecisionService:
        current = get_service()
        if current is None:
            raise EngineNotReadyError("The decision engine is still loading")
        return current

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @router.get("/ready", response_model=ReadyResponse, responses={503: {"model": ErrorResponse}})
    def ready():
        current = get_service()
        if current is None or not current.is_ready():
            return error_response(503, "MODEL_NOT_READY", "The decision engine is not ready")
        info = current.info()
        return ReadyResponse(status="ready", engine=info.name, model=info.model)

    @router.get("/v1/info", response_model=InfoResponse, responses=_ERRORS)
    def info() -> InfoResponse:
        current = service()
        engine = current.info()
        return InfoResponse(
            api_version=API_VERSION,
            version=__version__,
            engine=EngineInfoOut(
                name=engine.name,
                model=engine.model,
                revision=engine.revision,
                native_batch=engine.native_batch,
            ),
            available_engines=available_engines(),
            min_options=MIN_OPTIONS,
            max_options=MAX_OPTIONS,
            default_min_selected_probability=current.default_threshold,
            supported_modes=["direct", "shared"],
        )

    @router.post("/v1/decide", response_model=DecideResponse, responses=_ERRORS)
    def decide(request: DecideRequest) -> DecideResponse:
        result = service().decide(
            state=request.state,
            decision=_to_decision(request, request.min_selected_probability),
        )
        return _to_response(result)

    @router.post("/v1/decide/batch", response_model=BatchDecideResponse, responses=_ERRORS)
    def decide_batch(request: BatchDecideRequest) -> BatchDecideResponse:
        decisions = [
            _to_decision(
                item,
                item.min_selected_probability
                if item.min_selected_probability is not None
                else request.min_selected_probability,
            )
            for item in request.decisions
        ]
        results = service().decide_batch(state=request.state, decisions=decisions)
        return BatchDecideResponse(decisions=[_to_response(r) for r in results])

    return router


def _to_decision(item: DecideRequest | BatchDecideItem, threshold: float | None) -> Decision:
    return Decision(
        question=item.question,
        options=tuple(Option(id=o.id, description=o.description) for o in item.options),
        min_selected_probability=threshold,
    )


def _to_response(result: DecisionResult) -> DecideResponse:
    return DecideResponse(
        decision=OptionIn(id=result.decision.id, description=result.decision.description),
        probabilities=result.probabilities,
        selected_probability=result.selected_probability,
        accepted=result.accepted,
        threshold=result.threshold,
        metadata=result.metadata,
    )
