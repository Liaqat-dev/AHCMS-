"""Persisted refresh-token session (one row per active device/login).

Auth design:

* On login, create a ``RefreshSession`` storing only a HASH of the refresh token
  (never the raw token) plus its ``jti``.
* On refresh, ROTATE: verify the presented token against ``token_hash``, then
  replace ``token_hash`` / ``jti`` and extend ``expires_at``.
* Concurrency cap: ``settings.MAX_SESSIONS_PER_USER`` (= 5). Before inserting a
  new session, if the subject already has 5 *active* sessions (``revoked_at IS
  NULL`` and not expired), revoke the OLDEST first — so a 6th device evicts the
  1st.

A session belongs to exactly one subject: a staff ``User`` **or** a ``Student``
(who is not a user at all). Both columns are nullable and a check constraint
enforces that precisely one is set.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import college_now
from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin

# Exactly one subject column is populated — never both, never neither.
_ONE_SUBJECT = CheckConstraint(
    "(user_id IS NOT NULL AND student_id IS NULL) OR (user_id IS NULL AND student_id IS NOT NULL)",
    name="ck_refresh_sessions_one_subject",
)


class RefreshSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "refresh_sessions"
    __table_args__ = (_ONE_SUBJECT,)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # Device / provenance metadata for the "your active sessions" view.
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=college_now,
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
