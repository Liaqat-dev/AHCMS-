"""Convert unhandled exceptions into the standard error envelope.

Registered inside ``CORSMiddleware`` and ``RequestIDMiddleware`` (see
``main.create_app``), so — unlike the ``Exception`` handler that runs at
Starlette's outermost ``ServerErrorMiddleware`` — the 500 response it returns
still receives CORS headers and carries the request correlation id in both the
envelope and the ``X-Request-ID`` header. It also wraps ``RateLimitMiddleware``,
so a failure inside the rate limiter gets the same envelope.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.exceptions.handlers import error_envelope

logger = logging.getLogger("app.error")


class CatchAllMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            logger.exception(
                "Unhandled exception: %s",
                exc,
                extra={"method": request.method, "path": request.url.path},
            )
            return error_envelope(500, "internal_error", "Internal server error")
