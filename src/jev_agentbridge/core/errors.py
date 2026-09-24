"""Domain errors. Adapters raise these; the API layer maps them to HTTP responses."""

from __future__ import annotations


class DecisionError(Exception):
    """Base class for errors that have a stable, documented error code."""

    code = "ENGINE_ERROR"
    status_code = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidDecisionError(DecisionError):
    """The request is well-formed JSON but not a valid decision."""

    code = "INVALID_REQUEST"
    status_code = 400


class DuplicateOptionIdError(InvalidDecisionError):
    code = "DUPLICATE_OPTION_ID"


class OptionCountError(InvalidDecisionError):
    code = "INVALID_OPTIONS"


class InputTooLargeError(InvalidDecisionError):
    code = "INPUT_TOO_LARGE"
    status_code = 413


class EngineNotReadyError(DecisionError):
    code = "MODEL_NOT_READY"
    status_code = 503


class EngineUnavailableError(DecisionError):
    """A remote backend (e.g. a RizzoFlow server) could not be reached."""

    code = "ENGINE_UNAVAILABLE"
    status_code = 503


class EngineError(DecisionError):
    """The adapter failed or returned something outside the contract."""

    code = "ENGINE_ERROR"
    status_code = 500
