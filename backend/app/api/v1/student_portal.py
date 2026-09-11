"""Student portal: roll-number login and the student's own profile.

Deliberately minimal and entirely read-only. A student is not a ``User``, holds
no roles and no permissions, and this is the entire surface available to them — a student
access token is refused by every staff endpoint (see ``app.api.deps``).

The refresh cookie has its own name and path (``STUDENT_REFRESH_COOKIE_*``) so
a student login and a staff login in the same browser cannot overwrite each
other, and ``rotate_session(expect="student")`` makes sure a staff cookie can
never be refreshed here even if one is presented.
"""

from __future__ import annotations

import math
import time
from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status
from limits import parse

from app.api.deps import CurrentStudent, DBSession, Pagination
from app.api.v1.attendance import student_report
from app.core.config import settings
from app.core.rate_limit import check
from app.exceptions.errors import RateLimited, Unauthorized
from app.schemas.attendance import StudentAttendanceOut
from app.schemas.auth import (
    AuthenticatedStudent,
    StudentLoginRequest,
    StudentTokenResponse,
)
from app.schemas.enrollment import EnrollmentOut
from app.services import auth as auth_service
from app.services import enrollments as enrollments_service

# Login/refresh/logout live under the auth prefix so the httpOnly refresh
# cookie's path scope covers them.
auth_router = APIRouter(prefix="/auth/student", tags=["student-auth"])
# The portal itself.
portal_router = APIRouter(prefix="/student", tags=["student-portal"])

_login_limit = parse(settings.RATE_LIMIT_LOGIN)


def _set_refresh_cookie(response: Response, value: str) -> None:
    response.set_cookie(
        key=settings.STUDENT_REFRESH_COOKIE_NAME,
        value=value,
        max_age=settings.REFRESH_TOKEN_TTL,
        path=settings.STUDENT_REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.STUDENT_REFRESH_COOKIE_NAME,
        path=settings.STUDENT_REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


def _student_of(tokens: auth_service.IssuedTokens) -> AuthenticatedStudent:
    return AuthenticatedStudent.model_validate(tokens.subject)


def _token_response(tokens: auth_service.IssuedTokens) -> StudentTokenResponse:
    return StudentTokenResponse(
        access_token=tokens.access_token,
        expires_in=settings.ACCESS_TOKEN_TTL,
        student=_student_of(tokens),
    )


@auth_router.post("/login", response_model=StudentTokenResponse)
async def student_login(
    body: StudentLoginRequest, request: Request, response: Response, db: DBSession
):
    # Stricter, credential-stuffing-resistant limit than the global default.
    if settings.RATE_LIMIT_ENABLED:
        client = request.client.host if request.client else "anonymous"
        result = await check(f"student-login:{client}", _login_limit)
        if not result.allowed:
            retry_after = max(1, math.ceil(result.reset_at - time.time()))
            raise RateLimited(headers={"Retry-After": str(retry_after)})

    student = await auth_service.authenticate_student(db, body.roll_no, body.password)
    tokens = await auth_service.create_session(
        db,
        student,
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    _set_refresh_cookie(response, tokens.cookie_value)
    return _token_response(tokens)


@auth_router.post("/refresh", response_model=StudentTokenResponse)
async def student_refresh(request: Request, response: Response, db: DBSession):
    cookie = request.cookies.get(settings.STUDENT_REFRESH_COOKIE_NAME)
    if not cookie:
        raise Unauthorized("Missing refresh token")
    try:
        tokens = await auth_service.rotate_session(db, cookie, expect="student")
    except Unauthorized:
        # Persist reuse-detection revocations even though we reject the call.
        await db.commit()
        _clear_refresh_cookie(response)
        raise
    await db.commit()
    _set_refresh_cookie(response, tokens.cookie_value)
    return _token_response(tokens)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def student_logout(request: Request, response: Response, db: DBSession) -> None:
    cookie = request.cookies.get(settings.STUDENT_REFRESH_COOKIE_NAME)
    if cookie:
        await auth_service.revoke_session_by_cookie(db, cookie)
        await db.commit()
    _clear_refresh_cookie(response)


@portal_router.get("/me", response_model=AuthenticatedStudent)
async def student_me(auth: CurrentStudent) -> AuthenticatedStudent:
    return AuthenticatedStudent.model_validate(auth.student)


@portal_router.get("/me/enrollment", response_model=EnrollmentOut)
async def student_my_enrollment(auth: CurrentStudent, db: DBSession) -> EnrollmentOut:
    """The student's own class and chosen subjects.

    Read-only on purpose: subject choice is recorded by staff, so the portal
    has no write surface here — a student token can still open nothing but its
    own rows.
    """
    return EnrollmentOut.from_enrollment(
        await enrollments_service.get_by_student(db, auth.student.id)
    )


@portal_router.get("/me/attendance", response_model=StudentAttendanceOut)
async def student_my_attendance(
    auth: CurrentStudent,
    pagination: Pagination,
    db: DBSession,
    date_from: Annotated[date_type | None, Query(description="Inclusive")] = None,
    date_to: Annotated[date_type | None, Query(description="Inclusive")] = None,
) -> StudentAttendanceOut:
    """The student's own register history and percentage. Read-only."""
    return await student_report(
        db, auth.student.id, pagination=pagination, date_from=date_from, date_to=date_to
    )
