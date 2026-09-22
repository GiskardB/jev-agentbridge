"""JEV-CPU-AgentBridge entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI

from .api.errors import BridgeError
from .api.routes import create_router
from .engine.base import DecisionEngine
from .runtime.settings import Settings

if TYPE_CHECKING:
    pass

app = FastAPI(title="JEV-CPU-AgentBridge", version="0.2.0")

_settings = Settings.from_env()


@app.on_event("startup")
async def startup() -> None:
    """Load the configured decision engine (JEV_ENGINE)."""
    from .engine.registry import create_engine

    app.state.engine = create_engine(_settings)


@app.on_event("shutdown")
async def shutdown() -> None:
    """Clean up resources on shutdown."""
    pass


def get_engine() -> DecisionEngine:
    """Get the decision engine from app state."""
    engine = getattr(app.state, "engine", None)
    if engine is None:
        raise RuntimeError("Engine not initialized. Call startup event first.")
    return engine


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