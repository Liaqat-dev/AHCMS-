"""Per-client, per-path rate limiting.

Keyed by client IP + request path (mirroring a per-endpoint limit). On breach it
returns the standard error envelope with a ``Retry-After`` header; successful
responses carry ``X-RateLimit-*`` headers. Disabled via ``RATE_LIMIT_ENABLED``.
"""

from __future__ import annotations

import math
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.rate_limit import check
from app.exceptions.handlers import error_envelope


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        client = request.client.host if request.client else "anonymous"
        result = await check(f"{client}:{request.url.path}")

        if not result.allowed:
            retry_after = max(1, math.ceil(result.reset_at - time.time()))
            limited = error_envelope(
                429, "rate_limited", "Too many requests", {"limit": str(result.limit)}
            )
            limited.headers["Retry-After"] = str(retry_after)
            return limited

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(result.limit.amount)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        return response
