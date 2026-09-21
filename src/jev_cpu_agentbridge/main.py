"""JEV-CPU-AgentBridge entry point."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

from fastapi import FastAPI

from .api.errors import BridgeError
from .api.routes import create_router
from .runtime.settings import Settings
from .engine.semif import SemIfEngine
from .engine.base import DecisionEngine

if TYPE_CHECKING:
    pass

app = FastAPI(title="JEV-CPU-AgentBridge", version="0.1.0")

_settings = Settings.from_env()

_engine_ctx: ContextVar[DecisionEngine | None] = ContextVar("engine")


def get_engine() -> DecisionEngine:
    """Get the decision engine from context."""
    try:
        engine = _engine_ctx.get()
    except LookupError:
        raise RuntimeError("Engine not initialized. Call startup event first.")
    if engine is None:
        raise RuntimeError("Engine not initialized. Call startup event first.")
    return engine


@app.on_event("startup")
async def startup() -> None:
    """Load the model and initialize the engine."""
    from .runtime.model_loader import ModelLoader

    loaded = ModelLoader(_settings).load()
    engine = SemIfEngine(
        model=loaded.model,
        tokenizer=loaded.tokenizer,
        model_name=_settings.model_name,
        model_revision=_settings.model_revision,
        max_input_tokens=_settings.max_input_tokens,
        min_selected_probability=_settings.min_selected_probability,
    )
    engine._ready = True  # noqa: SLF001
    _engine_ctx.set(engine)


@app.on_event("shutdown")
async def shutdown() -> None:
    """Clean up resources on shutdown."""
    pass


app.include_router(create_router(get_engine, _settings))


@app.exception_handler(BridgeError)
async def bridge_error_handler(request, error: BridgeError):
    return {"error": error.to_response()["error"]}


def main() -> None:
    """Run the service with Uvicorn."""
    import uvicorn

    uvicorn.run(app, host=_settings.host, port=_settings.port)


if __name__ == "__main__":
    main()