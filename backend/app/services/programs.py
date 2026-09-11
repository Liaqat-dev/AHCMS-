"""Programs — courses of study ("Engineering" / ``ENG``).

Reading is granted to teachers by default; creating, renaming and deleting need
``programs:write``, which is seeded only to ``super_admin``.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Class, Program
from app.exceptions.errors import BadRequest, Conflict, NotFound

#: Columns a PATCH may set. Anything else is a client error rather than
#: something to silently ignore.
UPDATABLE_FIELDS = frozenset({"name", "code"})

#: ProgramOut always renders the creator's name, so load it in the same round
#: trip — the relationship is `lazy="raise"`, which would otherwise blow up
#: rather than quietly emitting an N+1.
_WITH_CREATOR = selectinload(Program.created_by)


async def get_program(db: AsyncSession, program_id: uuid.UUID) -> Program:
    program = await db.scalar(
        select(Program).where(Program.id == program_id).options(_WITH_CREATOR)
    )
    if program is None:
        raise NotFound("Program not found")
    return program


async def list_programs(
    db: AsyncSession, *, limit: int, offset: int, q: str | None = None
) -> tuple[list[Program], int]:
    total_query = select(func.count()).select_from(Program)
    list_query = select(Program).options(_WITH_CREATOR)

    if q:
        term = f"%{q.strip()}%"
        condition = or_(Program.name.ilike(term), Program.code.ilike(term))
        total_query = total_query.where(condition)
        list_query = list_query.where(condition)

    total = await db.scalar(total_query) or 0
    programs = (
        await db.scalars(list_query.order_by(Program.name).limit(limit).offset(offset))
    ).all()
    return list(programs), total


async def _assert_unique(
    db: AsyncSession,
    *,
    name: str | None = None,
    code: str | None = None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """Guard both unique columns with a clear 409 instead of an IntegrityError."""
    for column, value, label in (
        (Program.name, name, "name"),
        (Program.code, code, "code"),
    ):
        if value is None:
            continue
        query = select(Program.id).where(func.lower(column) == value.lower())
        if exclude_id is not None:
            query = query.where(Program.id != exclude_id)
        if await db.scalar(query):
            raise Conflict(f"A program with this {label} already exists")


async def create_program(
    db: AsyncSession, *, name: str, code: str, created_by_id: uuid.UUID | None
) -> Program:
    await _assert_unique(db, name=name, code=code)

    program = Program(name=name, code=code, created_by_id=created_by_id)
    db.add(program)
    await db.flush()
    # created_by is `lazy="raise"`; the caller renders it, so refetch the row
    # with the creator joined rather than touching the unloaded relationship.
    return await get_program(db, program.id)


async def update_program(
    db: AsyncSession, program_id: uuid.UUID, changes: dict[str, Any]
) -> Program:
    """Apply a partial update.

    ``changes`` must come from ``model_dump(exclude_unset=True)`` — an omitted
    field has to stay untouched, not be overwritten with the schema's ``None``
    default.
    """
    unknown = set(changes) - UPDATABLE_FIELDS
    if unknown:
        raise BadRequest("Unknown fields", details={"fields": sorted(unknown)})

    program = await get_program(db, program_id)
    await _assert_unique(
        db, name=changes.get("name"), code=changes.get("code"), exclude_id=program.id
    )

    for field, value in changes.items():
        setattr(program, field, value)
    await db.flush()
    return program


async def delete_program(db: AsyncSession, program_id: uuid.UUID) -> None:
    program = await get_program(db, program_id)

    # Classes are ON DELETE RESTRICT, so this would otherwise surface as an
    # IntegrityError (a 500) at flush time. Say what is actually in the way.
    # `Class` is used directly rather than through `services.classes`, which
    # imports this module — going the other way too would be a cycle.
    class_count = (
        await db.scalar(
            select(func.count()).select_from(Class).where(Class.program_id == program.id)
        )
        or 0
    )
    if class_count:
        raise Conflict(f"This program still has {class_count} class(es); delete or move them first")

    await db.delete(program)
    await db.flush()
