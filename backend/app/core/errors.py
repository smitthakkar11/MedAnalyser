"""Application error types and the HTTP handlers that render them.

Errors are surfaced to clients as a stable JSON envelope::

    {"error": {"code": "not_found", "message": "...", "details": {...}}}

Unexpected exceptions are logged with a stack trace but reported to the client
as a generic message, so that internal details never leak.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for expected, client-reportable application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "The requested resource was not found."


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"
    message = "The request payload is invalid."


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "authentication_error"
    message = "Authentication is required."


class PermissionDeniedError(AppError):
    """Raised when an authenticated user does not own the requested resource."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    message = "You do not have access to this resource."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "The request conflicts with the current state of the resource."


class ServiceUnavailableError(AppError):
    """Raised when a dependency (database, LLM, storage) is unreachable."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"
    message = "A required service is currently unavailable."


def sanitise_validation_errors(
    errors: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Reduce Pydantic validation errors to a safe, serialisable shape.

    Two reasons this is not `exc.errors()` verbatim:

    1. **Never echo the input.** Pydantic includes the offending value under
       `input`, which for a signup request is the user's plaintext password.
       That value must not travel back in a response or into a log.
    2. **Stay serialisable.** Custom validators put the original exception
       object in `ctx`, which JSON cannot encode.
    """
    return [
        {
            "type": str(error.get("type", "value_error")),
            "field": ".".join(str(part) for part in error.get("loc", ()) if part != "body"),
            "message": _clean_message(str(error.get("msg", "Invalid value."))),
        }
        for error in errors
    ]


#: Prefixes Pydantic prepends to messages raised by custom validators. They are
#: implementation noise to anyone reading the form.
_MESSAGE_PREFIXES = ("Value error, ", "Assertion failed, ")


def _clean_message(message: str) -> str:
    for prefix in _MESSAGE_PREFIXES:
        if message.startswith(prefix):
            return message[len(prefix) :]
    return message


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    request_id = request_id_var.get()
    if request_id:
        body["error"]["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the JSON error envelope handlers to *app*."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(
            exc.status_code,
            f"http_{exc.status_code}",
            str(exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation_error",
            "The request payload is invalid.",
            {"errors": sanitise_validation_errors(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception",
            extra={"path": request.url.path, "method": request.method},
            exc_info=exc,
        )
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred.",
        )
