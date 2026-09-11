"""Shared FastAPI dependencies: DB session, pagination, auth context, RBAC guards.

Two principal types exist and are kept strictly apart by the access token's
``sub_type`` claim: a staff ``User`` (carries roles/permissions) and a
``Student`` (carries neither, and reaches only the student portal). A token of
the wrong kind is rejected with 403 rather than falling through to a permission
check, so a student token can never satisfy a staff route.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.models import Student, User
from app.db.session import get_db
from app.exceptions.errors import Forbidden, Unauthorized

_BEARER_401_HEADERS = {"WWW-Authenticate": "Bearer"}
_INVALID_TOKEN = "Invalid or expired token"

DBSession = Annotated[AsyncSession, Depends(get_db)]


class PaginationParams:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


Pagination = Annotated[PaginationParams, Depends()]


@dataclass(slots=True)
class AuthContext:
    """The authenticated staff user plus the claims baked into its access token.

    ``roles``/``permissions`` come from the TOKEN (not a live DB read) by
    design: permission checks cost nothing per request, and RBAC changes take
    effect on the next refresh/login (access TTL is 15 minutes).
    """

    user: User
    roles: frozenset[str]
    permissions: frozenset[str]
    session_id: uuid.UUID | None


def _bearer_claims(request: Request) -> dict:
    """Decode the ``Authorization: Bearer`` access token, or raise 401."""
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthorized("Not authenticated", headers=_BEARER_401_HEADERS)

    try:
        claims = decode_token(token)
    except jwt.PyJWTError as exc:
        raise Unauthorized(_INVALID_TOKEN, headers=_BEARER_401_HEADERS) from exc
    if claims.get("type") != "access":
        raise Unauthorized(_INVALID_TOKEN, headers=_BEARER_401_HEADERS)
    return claims


def _subject_id(claims: dict) -> uuid.UUID:
    try:
        return uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise Unauthorized(_INVALID_TOKEN, headers=_BEARER_401_HEADERS) from exc


async def get_current_user(request: Request, db: DBSession) -> AuthContext:
    """Resolve the authenticated staff user from the bearer token."""
    claims = _bearer_claims(request)
    if claims.get("sub_type") != "user":
        # A valid student token on a staff route: the credential is genuine but
        # the principal is the wrong kind, which is a 403, not a 401.
        raise Forbidden("This endpoint requires a staff account")

    user = await db.get(User, _subject_id(claims))
    if user is None or not user.is_active:
        raise Unauthorized("Account is disabled", headers=_BEARER_401_HEADERS)

    sid = claims.get("sid")
    return AuthContext(
        user=user,
        roles=frozenset(claims.get("roles", ())),
        permissions=frozenset(claims.get("perms", ())),
        session_id=uuid.UUID(sid) if sid else None,
    )


CurrentUser = Annotated[AuthContext, Depends(get_current_user)]


@dataclass(slots=True)
class StudentContext:
    """The authenticated student. No roles, no permissions — by design."""

    student: Student
    session_id: uuid.UUID | None


async def get_current_student(request: Request, db: DBSession) -> StudentContext:
    """Resolve the authenticated student from the bearer token."""
    claims = _bearer_claims(request)
    if claims.get("sub_type") != "student":
        raise Forbidden("This endpoint requires a student account")

    student = await db.get(Student, _subject_id(claims))
    if student is None or not student.is_active:
        raise Unauthorized("Account is disabled", headers=_BEARER_401_HEADERS)

    sid = claims.get("sid")
    return StudentContext(student=student, session_id=uuid.UUID(sid) if sid else None)


CurrentStudent = Annotated[StudentContext, Depends(get_current_student)]


def require_permissions(*codes: str):
    """Dependency factory: 403 unless the token carries every listed permission."""

    async def _check(auth: CurrentUser) -> AuthContext:
        missing = [c for c in codes if c not in auth.permissions]
        if missing:
            raise Forbidden(details={"missing_permissions": missing})
        return auth

    return _check


def require_roles(*names: str):
    """Dependency factory: 403 unless the token carries at least one listed role."""

    async def _check(auth: CurrentUser) -> AuthContext:
        if not auth.roles.intersection(names):
            raise Forbidden(details={"required_roles": list(names)})
        return auth

    return _check
