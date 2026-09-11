"""Subject seat accounting.

``subjects.student_count`` is a cache of the ``subject_enrollments`` rows. This
module is its only writer, so the number cannot be typed in by hand and drift
from the rows behind it.

Both operations are a single conditional statement rather than a read followed
by a write: two people enrolling into the last seat would otherwise both read
"29 of 30" and both succeed. Postgres row-locks the subject for the duration of
the UPDATE, so exactly one of them gets it and the other sees zero rows back.
"""

from __future__ import annotations

import uuid

from sqlalchemy import case, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Subject
from app.exceptions.errors import Conflict


async def claim_seat(db: AsyncSession, subject: Subject) -> None:
    """Take one seat, or raise 409 if the subject is already full."""
    taken = await db.scalar(
        update(Subject)
        .where(Subject.id == subject.id, Subject.student_count < Subject.student_limit)
        .values(student_count=Subject.student_count + 1)
        .returning(Subject.student_count)
        .execution_options(synchronize_session=False)
    )
    if taken is None:
        # The row exists — the caller loaded it — so the only way to match
        # nothing is the student_count < student_limit guard.
        raise Conflict(
            f"{subject.name} is full",
            details={
                "subject_id": str(subject.id),
                "student_limit": subject.student_limit,
            },
        )
    # The in-memory object still holds the pre-update counter.
    db.expire(subject, ["student_count"])


async def release_seat(db: AsyncSession, subject_id: uuid.UUID) -> None:
    """Give one seat back. Floors at zero so a double release cannot go negative."""
    await db.execute(
        update(Subject)
        .where(Subject.id == subject_id)
        .values(student_count=case((Subject.student_count > 0, Subject.student_count - 1), else_=0))
        .execution_options(synchronize_session=False)
    )
