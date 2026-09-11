"""Reusable ORM column mixins.

``uuid.UUID`` and ``datetime`` annotations map to SQLAlchemy 2.0's dialect-aware
``Uuid`` / ``DateTime`` types (native ``uuid`` on Postgres).

**Timestamps come from the application, not the database.** Every column here
carries a Python ``default`` as well as a ``server_default``: the app supplies
the value on every insert it makes, and the server default is left in place
only as a backstop for rows written outside it (a migration, a manual SQL fix).

That is not belt and braces — it is the fix for a real failure. A database
whose clock runs ahead of the app's stamps ``enrolled_at`` in the future, and
since a register's roster is "students enrolled on or before this date", a
student enrolled today then cannot be marked present today. One clock decides
what time it is, and it is the one that also decides what "today" means (see
``app.core.clock``).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import college_now


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=college_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=college_now,
        onupdate=college_now,
        server_default=func.now(),
        nullable=False,
    )
