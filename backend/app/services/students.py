"""Student records and portal credentials (staff-facing operations).

Students are not ``User`` rows and hold no roles; the only thing they can do
with these credentials is sign in to their own portal.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.db.models import Class, Enrollment, Student
from app.exceptions.errors import BadRequest, Conflict, NotFound
from app.services import auth as auth_service
from app.services import sessions as sessions_service

#: Columns a PATCH may set. Anything else in the payload is a client error
#: rather than something to silently ignore.
UPDATABLE_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "b_form_cnic",
        "date_of_birth",
        "father_name",
        "father_cnic",
        "mother_name",
        "cell_no",
        "address",
        "last_school_name",
        "ssc_roll_no",
        "ssc_marks_obtained",
        "ssc_marks_total",
        "ssc_year",
        "email",
        "is_active",
    }
)

#: Loaders that pull everything StudentOut renders in the same round trip; a
#: lazy load here would be an N+1 on every list response — and the enrollment
#: relationship is lazy="raise", so it would be an error rather than a query.
_WITH_SESSION = (
    selectinload(Student.session),
    selectinload(Student.enrollment).selectinload(Enrollment.class_).selectinload(Class.program),
    selectinload(Student.enrollment).selectinload(Enrollment.subject_links),
)


async def get_student(db: AsyncSession, student_id: uuid.UUID) -> Student:
    student = await db.scalar(
        select(Student).where(Student.id == student_id).options(*_WITH_SESSION)
    )
    if student is None:
        raise NotFound("Student not found")
    return student


async def list_students(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    session_id: uuid.UUID | None = None,
    q: str | None = None,
) -> tuple[list[Student], int]:
    filters = []
    if session_id is not None:
        filters.append(Student.session_id == session_id)
    if q:
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                Student.roll_no.ilike(term),
                Student.first_name.ilike(term),
                Student.last_name.ilike(term),
                Student.b_form_cnic.ilike(term),
            )
        )

    total_query = select(func.count()).select_from(Student)
    list_query = select(Student).options(*_WITH_SESSION)
    for condition in filters:
        total_query = total_query.where(condition)
        list_query = list_query.where(condition)

    total = await db.scalar(total_query) or 0
    students = (
        await db.scalars(list_query.order_by(Student.roll_no).limit(limit).offset(offset))
    ).all()
    return list(students), total


async def _assert_unique(
    db: AsyncSession,
    *,
    email: str | None = None,
    b_form_cnic: str | None = None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """Guard the unique columns with a clear 409 instead of an IntegrityError."""
    for column, value, label in (
        (Student.email, email, "email"),
        (Student.b_form_cnic, b_form_cnic, "CNIC/B-Form number"),
    ):
        if value is None:
            continue
        query = select(Student.id).where(column == value)
        if exclude_id is not None:
            query = query.where(Student.id != exclude_id)
        if await db.scalar(query):
            raise Conflict(f"A student with this {label} already exists")


async def create_student(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    first_name: str,
    last_name: str,
    password: str | None = None,
    **fields: Any,
) -> Student:
    session = await sessions_service.get_session(db, session_id)

    email = fields.get("email")
    if email:
        fields["email"] = email = email.lower()
    await _assert_unique(db, email=email, b_form_cnic=fields.get("b_form_cnic"))

    student = Student(
        roll_no=await sessions_service.allocate_roll_no(db, session),
        session_id=session.id,
        first_name=first_name,
        last_name=last_name,
        hashed_password=hash_password(password) if password else None,
        **fields,
    )
    db.add(student)
    await db.flush()
    # The relationship is what StudentOut renders; populate it without a
    # second query now that the row exists.
    student.session = session
    return student


async def update_student(
    db: AsyncSession, student_id: uuid.UUID, changes: dict[str, Any]
) -> Student:
    """Apply a partial update.

    ``changes`` must come from ``model_dump(exclude_unset=True)`` — an omitted
    field has to stay untouched, not be overwritten with the schema's ``None``
    default.
    """
    unknown = set(changes) - UPDATABLE_FIELDS
    if unknown:
        raise BadRequest("Unknown fields", details={"fields": sorted(unknown)})

    student = await get_student(db, student_id)

    if changes.get("email"):
        changes["email"] = changes["email"].lower()
    await _assert_unique(
        db,
        email=changes.get("email"),
        b_form_cnic=changes.get("b_form_cnic"),
        exclude_id=student.id,
    )

    deactivating = changes.get("is_active") is False
    for field, value in changes.items():
        setattr(student, field, value)
    if deactivating:
        # Deactivation must not leave a usable portal session behind.
        await auth_service.revoke_all_sessions(db, student)

    await db.flush()
    return student


async def set_password(db: AsyncSession, student_id: uuid.UUID, password: str) -> Student:
    """Issue or reset the student's portal password.

    Existing sessions are revoked, so a password reset actually locks out
    whoever was signed in with the old one.
    """
    student = await get_student(db, student_id)
    student.hashed_password = hash_password(password)
    await auth_service.revoke_all_sessions(db, student)
    await db.flush()
    return student
