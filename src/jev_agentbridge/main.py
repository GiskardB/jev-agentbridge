"""JEV-AgentBridge entry point."""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from . import __version__
from .api.errors import install_error_handlers
from .api.routes import create_router
from .core.ports import DecisionAdapter
from .core.service import DecisionService
from .runtime.settings import Settings

logger = logging.getLogger("jev_agentbridge")


def create_app(
    settings: Settings | None = None,
    adapter: DecisionAdapter | None = None,
) -> FastAPI:
    """Build the app.

    Without `adapter`, the one named by `settings.engine` (JEV_ENGINE) is built at
    startup. Passing an adapter (tests, embedding) skips the registry entirely. The MCP
    endpoint (`/mcp`) is served by the same app and the same DecisionService.
    """

    settings = settings or Settings.from_env()
    mcp = None
    if settings.mcp_enabled:
        from .api.mcp import create_mcp_server

        mcp = create_mcp_server(lambda: app.state.service)
        # DNS-rebinding protection is on when bound to localhost and off on 0.0.0.0 (Docker).
        mcp_app = mcp.streamable_http_app(
            stateless_http=True, json_response=True, host=settings.host
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.service is None:
            from .adapters.registry import create_adapter

            logger.info("Loading decision engine %r", settings.engine)
            app.state.service = DecisionService(
                create_adapter(settings.engine),
                default_threshold=settings.min_selected_probability,
            )
        async with AsyncExitStack() as stack:
            if mcp is not None:
                await stack.enter_async_context(mcp.session_manager.run())
            yield

    app = FastAPI(title="JEV-AgentBridge", version=__version__, lifespan=lifespan)
    app.state.service = (
        DecisionService(adapter, default_threshold=settings.min_selected_probability)
        if adapter is not None
        else None
    )
    install_error_handlers(app)
    app.include_router(create_router(lambda: app.state.service))
    if mcp is not None:
        app.router.routes.extend(mcp_app.routes)  # POST/GET /mcp, streamable HTTP
    return app


app = create_app()


def main() -> None:
    """Run the service with Uvicorn."""
    import uvicorn

    settings = Settings.from_env()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
