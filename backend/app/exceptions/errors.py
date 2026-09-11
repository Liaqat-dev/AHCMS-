"""Application error hierarchy.

Raise these from anywhere in the app; ``exceptions.handlers`` turns each into a
consistent JSON error envelope with the right HTTP status code.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for expected, mapped application errors."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "Internal server error"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Any | None = None,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details
        self.headers = headers
        if code:
            self.code = code
        super().__init__(self.message)


class BadRequest(AppError):
    status_code = 400
    code = "bad_request"
    message = "Bad request"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Authentication required"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"
    message = "You do not have permission to perform this action"


class NotFound(AppError):
    status_code = 404
    code = "not_found"
    message = "Resource not found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"
    message = "Resource already exists or is in a conflicting state"


class Unprocessable(AppError):
    """Well-formed request that asks for something the domain cannot express.

    Distinct from ``Conflict``: a conflict may succeed on a retry (a full
    subject frees a seat), whereas this will never succeed unchanged (a subject
    that is simply not taught to the student's class).
    """

    status_code = 422
    code = "unprocessable"
    message = "Request cannot be processed"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"
    message = "Too many requests"


class ServiceUnavailable(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "Service temporarily unavailable"
