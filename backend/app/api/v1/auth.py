"""Staff auth endpoints: login, rotating refresh, logout, sessions, /me.

The access token is returned in the body (SPA keeps it in memory); the refresh
token travels only in an httpOnly cookie scoped to this router's path.

Students authenticate separately in ``app.api.v1.student_portal`` — they are
not ``User`` rows and never reach these endpoints.
"""

from __future__ import annotations

import math
import time
import uuid

from fastapi import APIRouter, Request, Response, status
from limits import parse

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.core.rate_limit import check
from app.db.models import User
from app.exceptions.errors import RateLimited, Unauthorized
from app.schemas.auth import AuthenticatedUser, LoginRequest, SessionInfo, TokenResponse
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_login_limit = parse(settings.RATE_LIMIT_LOGIN)


def _set_refresh_cookie(response: Response, value: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=value,
        max_age=settings.REFRESH_TOKEN_TTL,
        path=settings.REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


def _token_response(tokens: auth_service.IssuedTokens) -> TokenResponse:
    """Build the staff token payload. The subject is always a User here."""
    user = tokens.subject
    if not isinstance(user, User):  # pragma: no cover - rotate_session pins this
        raise Unauthorized("Invalid or expired session")
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=settings.ACCESS_TOKEN_TTL,
        user=AuthenticatedUser(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            roles=user.role_names,
            permissions=user.permission_codes,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, response: Response, db: DBSession):
    # Stricter, credential-stuffing-resistant limit than the global default.
    if settings.RATE_LIMIT_ENABLED:
        client = request.client.host if request.client else "anonymous"
        result = await check(f"login:{client}", _login_limit)
        if not result.allowed:
            retry_after = max(1, math.ceil(result.reset_at - time.time()))
            raise RateLimited(headers={"Retry-After": str(retry_after)})

    user = await auth_service.authenticate(db, body.email, body.password)
    tokens = await auth_service.create_session(
        db,
        user,
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    _set_refresh_cookie(response, tokens.cookie_value)
    return _token_response(tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, db: DBSession):
    cookie = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not cookie:
        raise Unauthorized("Missing refresh token")
    try:
        tokens = await auth_service.rotate_session(db, cookie, expect="user")
    except Unauthorized:
        # Persist reuse-detection revocations even though we reject the call.
        await db.commit()
        _clear_refresh_cookie(response)
        raise
    await db.commit()
    _set_refresh_cookie(response, tokens.cookie_value)
    return _token_response(tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, db: DBSession) -> None:
    cookie = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if cookie:
        await auth_service.revoke_session_by_cookie(db, cookie)
        await db.commit()
    _clear_refresh_cookie(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(auth: CurrentUser, response: Response, db: DBSession) -> None:
    await auth_service.revoke_all_sessions(db, auth.user)
    await db.commit()
    _clear_refresh_cookie(response)


@router.get("/me", response_model=AuthenticatedUser)
async def me(auth: CurrentUser) -> AuthenticatedUser:
    # Roles/permissions from the DB (fresh), not the token claims.
    return AuthenticatedUser(
        id=auth.user.id,
        email=auth.user.email,
        full_name=auth.user.full_name,
        roles=auth.user.role_names,
        permissions=auth.user.permission_codes,
    )


@router.get("/sessions", response_model=list[SessionInfo])
async def sessions(auth: CurrentUser, db: DBSession) -> list[SessionInfo]:
    return [
        SessionInfo(
            id=s.id,
            user_agent=s.user_agent,
            ip_address=s.ip_address,
            created_at=s.created_at,
            expires_at=s.expires_at,
            current=s.id == auth.session_id,
        )
        for s in await auth_service.list_sessions(db, auth.user)
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(session_id: uuid.UUID, auth: CurrentUser, db: DBSession) -> None:
    await auth_service.revoke_session(db, auth.user, session_id)
    await db.commit()
