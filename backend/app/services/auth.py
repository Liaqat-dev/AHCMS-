"""Authentication service: login, rotating refresh sessions, revocation.

Two kinds of principal share this machinery:

* a staff ``User``, who signs in with an email and carries roles/permissions;
* a ``Student``, who signs in with a roll number and carries neither — a
  student is not a user and can only reach their own portal.

Session model (see ``app.db.models.session``): one ``RefreshSession`` row per
device/login, owned by exactly one of the two. The refresh cookie is
``"{session_id}.{secret}"``; only the secret's hash is stored. On every refresh
the secret (and ``jti``) rotates but the session id is stable — so a replayed
*old* secret against a live session is detectable as token theft, and we revoke
the whole session.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    build_refresh_cookie,
    create_access_token,
    generate_refresh_secret,
    hash_password,
    hash_refresh_secret,
    password_needs_rehash,
    split_refresh_cookie,
    verify_password,
    verify_refresh_secret,
)
from app.db.models import RefreshSession, Student, User
from app.exceptions.errors import NotFound, Unauthorized

logger = logging.getLogger("app.auth")

_INVALID_CREDENTIALS = "Invalid email or password"
_INVALID_STUDENT_CREDENTIALS = "Invalid roll number or password"
_INVALID_SESSION = "Invalid or expired session"

#: A principal that can hold a refresh session.
SessionSubject = User | Student

#: Value of the access token's ``sub_type`` claim, which stops a student token
#: from ever satisfying a staff dependency (and vice versa). See ``api.deps``.
SubjectKind = Literal["user", "student"]


@dataclass(slots=True)
class IssuedTokens:
    access_token: str
    cookie_value: str
    subject: SessionSubject
    session_id: uuid.UUID


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes for timezone-aware columns; normalize."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _is_active_session(session: RefreshSession, now: datetime) -> bool:
    return session.revoked_at is None and _aware(session.expires_at) > now


def subject_kind(subject: SessionSubject) -> SubjectKind:
    return "student" if isinstance(subject, Student) else "user"


def _owned_by(subject: SessionSubject) -> ColumnElement[bool]:
    """Filter matching only the sessions belonging to this subject."""
    if isinstance(subject, Student):
        return RefreshSession.student_id == subject.id
    return RefreshSession.user_id == subject.id


def _build_access_token(subject: SessionSubject, session_id: uuid.UUID) -> str:
    claims: dict[str, object] = {
        "sid": str(session_id),
        "sub_type": subject_kind(subject),
    }
    if isinstance(subject, Student):
        claims["roll_no"] = subject.roll_no
    else:
        claims["roles"] = subject.role_names
        claims["perms"] = subject.permission_codes
    return create_access_token(str(subject.id), extra_claims=claims)


# ----- Credential checks -----------------------------------------------------


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    """Verify staff credentials; generic 401 for unknown email OR bad password."""
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.hashed_password):
        raise Unauthorized(_INVALID_CREDENTIALS)
    if not user.is_active:
        raise Unauthorized("Account is disabled")
    if password_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(password)
    return user


async def authenticate_student(db: AsyncSession, roll_no: str, password: str) -> Student:
    """Verify student portal credentials by roll number.

    A student with no password issued yet fails exactly like a wrong password,
    so the response never reveals which roll numbers exist.
    """
    student = await db.scalar(select(Student).where(Student.roll_no == roll_no.strip()))
    if (
        student is None
        or student.hashed_password is None
        or not verify_password(password, student.hashed_password)
    ):
        raise Unauthorized(_INVALID_STUDENT_CREDENTIALS)
    if not student.is_active:
        raise Unauthorized("Account is disabled")
    if password_needs_rehash(student.hashed_password):
        student.hashed_password = hash_password(password)
    return student


# ----- Sessions --------------------------------------------------------------


async def create_session(
    db: AsyncSession,
    subject: SessionSubject,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> IssuedTokens:
    """Open a new refresh session, evicting the oldest beyond the cap."""
    now = _now()
    active = (
        await db.scalars(
            select(RefreshSession)
            .where(
                _owned_by(subject),
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > now,
            )
            .order_by(RefreshSession.created_at)
        )
    ).all()
    # Evict oldest so the account never exceeds MAX_SESSIONS_PER_USER.
    excess = len(active) - settings.MAX_SESSIONS_PER_USER + 1
    for session in active[:excess] if excess > 0 else []:
        session.revoked_at = now
        logger.info("Session cap reached; evicted oldest session %s", session.id)

    secret = generate_refresh_secret()
    is_student = isinstance(subject, Student)
    session = RefreshSession(
        user_id=None if is_student else subject.id,
        student_id=subject.id if is_student else None,
        token_hash=hash_refresh_secret(secret),
        jti=uuid.uuid4().hex,
        user_agent=(user_agent or "")[:512] or None,
        ip_address=ip_address,
        expires_at=now + timedelta(seconds=settings.REFRESH_TOKEN_TTL),
    )
    db.add(session)
    await db.flush()  # assign session.id before building the cookie/token

    return IssuedTokens(
        access_token=_build_access_token(subject, session.id),
        cookie_value=build_refresh_cookie(session.id, secret),
        subject=subject,
        session_id=session.id,
    )


async def _load_subject(db: AsyncSession, session: RefreshSession) -> SessionSubject | None:
    if session.student_id is not None:
        return await db.get(Student, session.student_id)
    if session.user_id is not None:
        return await db.get(User, session.user_id)
    return None


async def rotate_session(
    db: AsyncSession, cookie_value: str, *, expect: SubjectKind | None = None
) -> IssuedTokens:
    """Validate the refresh cookie, rotate its secret, issue a new access token.

    ``expect`` pins the caller's principal type, so a student cookie presented
    to the staff refresh endpoint (or the reverse) is rejected rather than
    quietly issuing a token of the wrong kind.
    """
    parsed = split_refresh_cookie(cookie_value)
    if parsed is None:
        raise Unauthorized(_INVALID_SESSION)
    session_id, secret = parsed

    session = await db.get(RefreshSession, session_id)
    now = _now()
    if session is None or not _is_active_session(session, now):
        raise Unauthorized(_INVALID_SESSION)

    if not verify_refresh_secret(secret, session.token_hash):
        # Correct session id but a stale/foreign secret on a LIVE session:
        # almost certainly a replayed (stolen) token. Kill the session.
        session.revoked_at = now
        logger.warning(
            "Refresh token reuse detected; session revoked",
            extra={"session_id": str(session.id)},
        )
        raise Unauthorized("Session invalidated")

    subject = await _load_subject(db, session)
    if subject is None or not subject.is_active:
        session.revoked_at = now
        raise Unauthorized("Account is disabled")
    if expect is not None and subject_kind(subject) != expect:
        raise Unauthorized(_INVALID_SESSION)

    new_secret = generate_refresh_secret()
    session.token_hash = hash_refresh_secret(new_secret)
    session.jti = uuid.uuid4().hex
    session.expires_at = now + timedelta(seconds=settings.REFRESH_TOKEN_TTL)

    return IssuedTokens(
        access_token=_build_access_token(subject, session.id),
        cookie_value=build_refresh_cookie(session.id, new_secret),
        subject=subject,
        session_id=session.id,
    )


async def revoke_session_by_cookie(db: AsyncSession, cookie_value: str) -> None:
    """Best-effort logout: revoke the cookie's session if it is still valid."""
    parsed = split_refresh_cookie(cookie_value)
    if parsed is None:
        return
    session_id, secret = parsed
    session = await db.get(RefreshSession, session_id)
    if session is not None and verify_refresh_secret(secret, session.token_hash):
        session.revoked_at = _now()


async def revoke_session(db: AsyncSession, subject: SessionSubject, session_id: uuid.UUID) -> None:
    """Revoke one of the subject's own sessions (404 if not theirs / unknown)."""
    session = await db.get(RefreshSession, session_id)
    now = _now()
    if session is None or not _is_active_session(session, now):
        raise NotFound("Session not found")
    owner_id = session.student_id if isinstance(subject, Student) else session.user_id
    if owner_id != subject.id:
        raise NotFound("Session not found")
    session.revoked_at = now


async def revoke_all_sessions(db: AsyncSession, subject: SessionSubject) -> int:
    now = _now()
    sessions = (
        await db.scalars(
            select(RefreshSession).where(
                _owned_by(subject),
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > now,
            )
        )
    ).all()
    for session in sessions:
        session.revoked_at = now
    return len(sessions)


async def list_sessions(db: AsyncSession, subject: SessionSubject) -> list[RefreshSession]:
    return list(
        await db.scalars(
            select(RefreshSession)
            .where(
                _owned_by(subject),
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > _now(),
            )
            .order_by(RefreshSession.created_at.desc())
        )
    )
