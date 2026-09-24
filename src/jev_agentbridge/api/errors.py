"""One error envelope for every failure: {"error": {"code", "message", "request_id"}}."""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..core.errors import DecisionError

logger = logging.getLogger("jev_agentbridge")


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    request_id = str(uuid.uuid4())
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DecisionError)
    async def _decision_error(_: Request, error: DecisionError) -> JSONResponse:
        if error.status_code >= 500:
            logger.error("%s: %s", error.code, error.message)
        return error_response(error.status_code, error.code, error.message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        details = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        )
        return error_response(422, "INVALID_REQUEST", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
        return error_response(error.status_code, "HTTP_ERROR", str(error.detail))
