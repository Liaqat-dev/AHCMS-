"""Global exception handlers → one consistent JSON error envelope.

Every error path (mapped ``AppError``s, request validation, rate limiting,
raw ``HTTPException``s, and unhandled 500s) returns::

    {"error": {"code", "message", "details", "request_id"}}

Unhandled exceptions are normally converted by ``CatchAllMiddleware`` (which
runs inside the CORS and request-id middleware, so those headers survive); the
``Exception`` handler registered here is only a last-resort safety net for
errors raised outside that middleware.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_ctx
from app.exceptions.errors import AppError
from app.schemas.common import ErrorDetail, ErrorResponse

logger = logging.getLogger("app.error")

REQUEST_ID_HEADER = "X-Request-ID"


def error_envelope(
    status_code: int,
    code: str,
    message: str,
    details: object = None,
    *,
    headers: Mapping[str, str] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    """Build the standard error envelope response (also used by middleware)."""
    request_id = request_id or request_id_ctx.get()
    body = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
            request_id=request_id,
        )
    )
    response = JSONResponse(
        status_code=status_code, content=jsonable_encoder(body), headers=headers
    )
    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id
    return response


def _sanitized_validation_errors(exc: RequestValidationError) -> list[dict[str, object]]:
    """Keep only safe fields — ``input``/``ctx`` can echo submitted secrets."""
    return [
        {"loc": err.get("loc", ()), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_envelope(
            exc.status_code, exc.code, exc.message, exc.details, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error_envelope(
            422,
            "validation_error",
            "Request validation failed",
            _sanitized_validation_errors(exc),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, str):
            message, details = exc.detail, None
        else:
            message, details = "HTTP error", exc.detail
        return error_envelope(
            exc.status_code,
            f"http_{exc.status_code}",
            message,
            details,
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def _handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Runs at Starlette's ServerErrorMiddleware, outside our middleware —
        # the request-id context var is already reset, so read request.state.
        request_id = getattr(request.state, "request_id", None)
        logger.exception(
            "Unhandled exception: %s",
            exc,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )
        return error_envelope(500, "internal_error", "Internal server error", request_id=request_id)
