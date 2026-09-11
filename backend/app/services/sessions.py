"""Academic sessions (student batches) and roll-number allocation.

Creating a batch is guarded by ``sessions:write``; a teacher gets it only if a
super-admin grants it to their role at runtime.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AcademicSession, Student
from app.db.models.academic_session import SESSION_LENGTH_YEARS
from app.exceptions.errors import Conflict, NotFound

#: Width of the per-session counter in a roll number ("2022-001").
ROLL_SEQ_WIDTH = 3


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> AcademicSession:
    session = await db.get(AcademicSession, session_id)
    if session is None:
        raise NotFound("Academic session not found")
    return session


async def list_sessions(
    db: AsyncSession, *, limit: int, offset: int
) -> tuple[list[tuple[AcademicSession, int]], int]:
    """Batches newest-first, each with how many students it holds."""
    total = await db.scalar(select(func.count()).select_from(AcademicSession)) or 0
    rows = (
        await db.execute(
            select(AcademicSession, func.count(Student.id))
            .outerjoin(Student, Student.session_id == AcademicSession.id)
            .group_by(AcademicSession.id)
            .order_by(AcademicSession.start_year.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [(row[0], row[1]) for row in rows], total


async def create_session(db: AsyncSession, *, start_year: int) -> AcademicSession:
    if await db.scalar(select(AcademicSession.id).where(AcademicSession.start_year == start_year)):
        raise Conflict(
            f"The {start_year}-{start_year + SESSION_LENGTH_YEARS} session already exists"
        )

    session = AcademicSession(start_year=start_year)
    db.add(session)
    await db.flush()
    return session


async def allocate_roll_no(db: AsyncSession, session: AcademicSession) -> str:
    """Reserve the next roll number in this batch, e.g. ``"2022-001"``.

    The counter is bumped with a single ``UPDATE ... RETURNING``, so Postgres
    row-locks it and two concurrent admissions cannot be handed the same
    number.
    """
    # RETURNING yields the value *after* the increment, so the number reserved
    # for this caller is one less.
    next_seq = await db.scalar(
        update(AcademicSession)
        .where(AcademicSession.id == session.id)
        .values(next_roll_seq=AcademicSession.next_roll_seq + 1)
        .returning(AcademicSession.next_roll_seq)
        .execution_options(synchronize_session=False)
    )
    if next_seq is None:  # pragma: no cover - the row was just loaded
        raise NotFound("Academic session not found")

    # The in-memory object still holds the pre-update counter.
    db.expire(session, ["next_roll_seq"])

    return f"{session.start_year}-{next_seq - 1:0{ROLL_SEQ_WIDTH}d}"
