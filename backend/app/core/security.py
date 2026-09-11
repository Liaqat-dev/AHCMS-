"""Password hashing (Argon2), JWT helpers, and refresh-token primitives.

Refresh tokens are opaque: the cookie value is ``"{session_id}.{secret}"``
where ``secret`` is high-entropy random. The server stores only
``sha256(secret)`` (argon2 is unnecessary for 384-bit random secrets and would
slow every refresh); the session id gives an O(1) primary-key lookup.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_needs_rehash(hashed: str) -> bool:
    """True when the stored hash uses outdated Argon2 parameters."""
    return _hasher.check_needs_rehash(hashed)


def create_access_token(
    subject: str,
    *,
    expires_in: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(seconds=expires_in or settings.ACCESS_TOKEN_TTL)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode/verify a JWT. Raises ``jwt.PyJWTError`` subclasses on failure."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


# ----- Refresh tokens (opaque, rotating) ------------------------------------


def generate_refresh_secret() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def verify_refresh_secret(secret: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_refresh_secret(secret), token_hash)


def build_refresh_cookie(session_id: uuid.UUID, secret: str) -> str:
    return f"{session_id}.{secret}"


def split_refresh_cookie(value: str) -> tuple[uuid.UUID, str] | None:
    """Parse ``"{session_id}.{secret}"``; None if malformed."""
    session_id, sep, secret = value.partition(".")
    if not sep or not secret:
        return None
    try:
        return uuid.UUID(session_id), secret
    except ValueError:
        return None
