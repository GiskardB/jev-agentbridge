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
from ..core.models import (
    MAX_OPTIONS,
    MIN_OPTIONS,
    QUESTION_TYPES,
    Decision,
    DecisionResult,
    Option,
)
from ..core.service import DecisionService
from .errors import error_response
from .schemas import (
    BatchDecideRequest,
    BatchDecideResponse,
    DecideRequest,
    DecideResponse,
    DecisionIn,
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
                native_types=[t for t in QUESTION_TYPES if t in current.native_types()],
            ),
            available_engines=available_engines(),
            min_options=MIN_OPTIONS,
            max_options=MAX_OPTIONS,
            default_min_selected_probability=current.default_threshold,
            supported_modes=["direct", "shared"],
            supported_types=list(QUESTION_TYPES),
            default_score_tolerance=current.default_score_tolerance,
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


def _to_decision(item: DecisionIn, threshold: float | None) -> Decision:
    if item.type == "noul":
        return Decision.noul(
            item.question,
            yes_description=item.yes_description,
            no_description=item.no_description,
            min_selected_probability=threshold,
        )
    return Decision(
        question=item.question,
        options=tuple(Option(id=o.id, description=o.description) for o in item.options or ()),
        min_selected_probability=threshold,
        type=item.type,
        score_tolerance=item.score_tolerance,
    )


def _to_response(result: DecisionResult) -> DecideResponse:
    return DecideResponse(
        type=result.type,
        decision=OptionIn(id=result.decision.id, description=result.decision.description),
        probabilities=result.probabilities,
        selected_probability=result.selected_probability,
        accepted=result.accepted,
        threshold=result.threshold,
        score=result.score,
        noul=result.noul,
        score_window_probability=result.score_window_probability,
        score_tolerance=result.score_tolerance,
        metadata=result.metadata,
    )
