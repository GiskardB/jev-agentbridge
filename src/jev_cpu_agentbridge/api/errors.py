"""Structured API errors."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException


class ErrorCode:
    """Valid error codes."""

    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_OPTIONS = "INVALID_OPTIONS"
    DUPLICATE_OPTION_ID = "DUPLICATE_OPTION_ID"
    TOO_MANY_OPTIONS = "TOO_MANY_OPTIONS"
    TOO_FEW_OPTIONS = "TOO_FEW_OPTIONS"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    TOKEN_SLOT_INVALID = "TOKEN_SLOT_INVALID"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    MODEL_NOT_READY = "MODEL_NOT_READY"
    ENGINE_ERROR = "ENGINE_ERROR"
    UNSUPPORTED_MODE = "UNSUPPORTED_MODE"


class BridgeError(HTTPException):
    """Structured bridge error."""

    def __init__(self, *, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.request_id = str(uuid.uuid4())
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message, "request_id": self.request_id},
        )

    def to_response(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": self.request_id,
            }
        }
