"""Faculty records (staff-facing).

Faculty are not ``User`` rows and hold no permissions; this is a personnel
register, not an account system.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Faculty, Subject, User
from app.exceptions.errors import BadRequest, Conflict, NotFound

#: Columns a PATCH may set. Anything else in the payload is a client error
#: rather than something to silently ignore.
UPDATABLE_FIELDS = frozenset(
    {
        "employee_no",
        "first_name",
        "last_name",
        "designation",
        "qualification",
        "cnic",
        "email",
        "cell_no",
        "address",
        "joined_on",
        "user_id",
        "is_active",
    }
)


async def get_member(db: AsyncSession, faculty_id: uuid.UUID) -> Faculty:
    member = await db.get(Faculty, faculty_id)
    if member is None:
        raise NotFound("Faculty member not found")
    return member


async def list_members(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    q: str | None = None,
    is_active: bool | None = None,
) -> tuple[list[Faculty], int]:
    filters: list[ColumnElement[bool]] = []
    if is_active is not None:
        filters.append(Faculty.is_active.is_(is_active))
    if q:
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                Faculty.employee_no.ilike(term),
                Faculty.first_name.ilike(term),
                Faculty.last_name.ilike(term),
                Faculty.designation.ilike(term),
                Faculty.cnic.ilike(term),
            )
        )

    total_query = select(func.count()).select_from(Faculty)
    list_query = select(Faculty)
    for condition in filters:
        total_query = total_query.where(condition)
        list_query = list_query.where(condition)

    total = await db.scalar(total_query) or 0
    members = (
        await db.scalars(
            list_query.order_by(Faculty.employee_no).limit(limit).offset(offset)
        )
    ).all()
    return list(members), total


async def _assert_account_free(
    db: AsyncSession, user_id: uuid.UUID | None, exclude_id: uuid.UUID | None = None
) -> None:
    """One login belongs to one person.

    The unique index would catch this, but an IntegrityError is a 500; naming
    who already holds the account is a 409 somebody can act on.
    """
    if user_id is None:
        return
    if not await db.scalar(select(User.id).where(User.id == user_id)):
        raise NotFound("Staff account not found", details={"user_id": str(user_id)})

    query = select(Faculty.employee_no).where(Faculty.user_id == user_id)
    if exclude_id is not None:
        query = query.where(Faculty.id != exclude_id)
    holder = await db.scalar(query)
    if holder:
        raise Conflict(f"That staff account is already linked to {holder}")


async def _assert_unique(
    db: AsyncSession,
    *,
    employee_no: str | None = None,
    email: str | None = None,
    cnic: str | None = None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """Guard the unique columns with a clear 409 instead of an IntegrityError."""
    for column, value, label in (
        (Faculty.employee_no, employee_no, "employee number"),
        (Faculty.email, email, "email"),
        (Faculty.cnic, cnic, "CNIC"),
    ):
        if value is None:
            continue
        query = select(Faculty.id).where(func.lower(column) == value.lower())
        if exclude_id is not None:
            query = query.where(Faculty.id != exclude_id)
        if await db.scalar(query):
            raise Conflict(f"A faculty member with this {label} already exists")


async def create_member(
    db: AsyncSession, *, employee_no: str, first_name: str, last_name: str, **fields: Any
) -> Faculty:
    email = fields.get("email")
    if email:
        fields["email"] = email = email.lower()
    await _assert_unique(db, employee_no=employee_no, email=email, cnic=fields.get("cnic"))
    await _assert_account_free(db, fields.get("user_id"))

    member = Faculty(
        employee_no=employee_no.strip(),
        first_name=first_name,
        last_name=last_name,
        **fields,
    )
    db.add(member)
    await db.flush()
    return member


async def update_member(
    db: AsyncSession, faculty_id: uuid.UUID, changes: dict[str, Any]
) -> Faculty:
    """Apply a partial update.

    ``changes`` must come from ``model_dump(exclude_unset=True)`` — an omitted
    field has to stay untouched, not be overwritten with the schema's ``None``
    default.
    """
    unknown = set(changes) - UPDATABLE_FIELDS
    if unknown:
        raise BadRequest("Unknown fields", details={"fields": sorted(unknown)})

    member = await get_member(db, faculty_id)

    if changes.get("email"):
        changes["email"] = changes["email"].lower()
    await _assert_unique(
        db,
        employee_no=changes.get("employee_no"),
        email=changes.get("email"),
        cnic=changes.get("cnic"),
        exclude_id=member.id,
    )
    if "user_id" in changes:
        await _assert_account_free(db, changes["user_id"], exclude_id=member.id)

    for field, value in changes.items():
        setattr(member, field, value)
    await db.flush()
    return member


async def delete_member(db: AsyncSession, faculty_id: uuid.UUID) -> None:
    """Remove the record outright.

    Refused while they still teach something: the subject would lose its
    teacher as a side effect of tidying a personnel file, and nobody would
    notice until a timetable was printed. Marking them former is the usual
    answer, and it keeps them nameable on old records.
    """
    member = await get_member(db, faculty_id)

    teaching = (
        await db.execute(
            select(Subject.code, Subject.name).where(Subject.teacher_id == member.id)
        )
    ).all()
    if teaching:
        raise Conflict(
            f"{member.full_name} still teaches {len(teaching)} subject(s); "
            "reassign them or mark this member as former staff",
            details={"subjects": [{"code": c, "name": n} for c, n in teaching]},
        )

    await db.delete(member)
    await db.flush()
