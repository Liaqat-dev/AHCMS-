"""Classes — the teaching groups inside a program.

Reading is granted to teachers by default; creating, renaming, moving and
deleting need ``classes:write``, which is seeded only to ``super_admin``.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import AttendanceSheet, Class, Enrollment, Exam
from app.exceptions.errors import BadRequest, Conflict, NotFound
from app.services import programs as programs_service

#: Columns a PATCH may set. Anything else is a client error rather than
#: something to silently ignore.
UPDATABLE_FIELDS = frozenset({"name", "program_id"})

#: ClassOut always renders the program, so load it in the same round trip — the
#: relationship is `lazy="raise"`, which would otherwise blow up rather than
#: quietly emitting an N+1.
_WITH_PROGRAM = selectinload(Class.program)


async def get_class(db: AsyncSession, class_id: uuid.UUID) -> Class:
    class_ = await db.scalar(select(Class).where(Class.id == class_id).options(_WITH_PROGRAM))
    if class_ is None:
        raise NotFound("Class not found")
    return class_


async def list_classes(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    program_id: uuid.UUID | None = None,
    q: str | None = None,
) -> tuple[list[Class], int]:
    filters = []
    if program_id is not None:
        filters.append(Class.program_id == program_id)
    if q:
        filters.append(Class.name.ilike(f"%{q.strip()}%"))

    total_query = select(func.count()).select_from(Class)
    list_query = select(Class).options(_WITH_PROGRAM)
    for condition in filters:
        total_query = total_query.where(condition)
        list_query = list_query.where(condition)

    total = await db.scalar(total_query) or 0
    classes = (await db.scalars(list_query.order_by(Class.name).limit(limit).offset(offset))).all()
    return list(classes), total


async def _assert_unique(
    db: AsyncSession,
    *,
    program_id: uuid.UUID,
    name: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """A name is unique within its program, not globally.

    Checked here so a collision is a clear 409 rather than an IntegrityError
    from the composite unique constraint.
    """
    query = select(Class.id).where(
        Class.program_id == program_id, func.lower(Class.name) == name.lower()
    )
    if exclude_id is not None:
        query = query.where(Class.id != exclude_id)
    if await db.scalar(query):
        raise Conflict("This program already has a class with this name")


async def create_class(db: AsyncSession, *, name: str, program_id: uuid.UUID) -> Class:
    # 404s if the program does not exist, rather than surfacing a foreign key
    # violation from the flush.
    program = await programs_service.get_program(db, program_id)
    await _assert_unique(db, program_id=program.id, name=name)

    class_ = Class(name=name, program_id=program.id)
    db.add(class_)
    await db.flush()
    # `program` is lazy="raise"; the caller renders it, so populate it here
    # rather than leaving the relationship unloaded.
    class_.program = program
    return class_


async def update_class(db: AsyncSession, class_id: uuid.UUID, changes: dict[str, Any]) -> Class:
    """Apply a partial update.

    ``changes`` must come from ``model_dump(exclude_unset=True)`` — an omitted
    field has to stay untouched, not be overwritten with the schema's ``None``
    default.
    """
    unknown = set(changes) - UPDATABLE_FIELDS
    if unknown:
        raise BadRequest("Unknown fields", details={"fields": sorted(unknown)})

    class_ = await get_class(db, class_id)

    # Uniqueness is per program, so a rename and a move are the same check
    # against whichever pair the row will end up with.
    program = class_.program
    if "program_id" in changes and changes["program_id"] != class_.program_id:
        program = await programs_service.get_program(db, changes["program_id"])
    name = changes.get("name", class_.name)
    if changes:
        await _assert_unique(db, program_id=program.id, name=name, exclude_id=class_.id)

    for field, value in changes.items():
        setattr(class_, field, value)
    await db.flush()
    class_.program = program
    return class_


async def delete_class(db: AsyncSession, class_id: uuid.UUID) -> None:
    class_ = await get_class(db, class_id)

    # Enrollments are ON DELETE RESTRICT, so this would otherwise surface as an
    # IntegrityError (a 500) at flush time. `Enrollment` is used directly rather
    # than through `services.enrollments`, which imports this module — going the
    # other way too would be a cycle.
    enrolled = (
        await db.scalar(
            select(func.count()).select_from(Enrollment).where(Enrollment.class_id == class_.id)
        )
        or 0
    )
    if enrolled:
        raise Conflict(
            f"This class still has {enrolled} enrolled student(s); move or unenroll them first",
            details={"student_count": enrolled},
        )

    # Same reasoning for the registers behind it: a term of attendance should
    # not disappear on one click.
    sheets = (
        await db.scalar(
            select(func.count())
            .select_from(AttendanceSheet)
            .where(AttendanceSheet.class_id == class_.id)
        )
        or 0
    )
    if sheets:
        raise Conflict(
            f"This class has {sheets} attendance register(s); delete them first",
            details={"attendance_count": sheets},
        )

    exams = (
        await db.scalar(
            select(func.count()).select_from(Exam).where(Exam.class_id == class_.id)
        )
        or 0
    )
    if exams:
        raise Conflict(
            f"This class has {exams} exam(s) on record; delete them first",
            details={"exam_count": exams},
        )

    await db.delete(class_)
    await db.flush()
