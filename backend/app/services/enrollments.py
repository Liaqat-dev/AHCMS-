"""Enrollment: the one class a student belongs to, plus their optional subjects.

Two rules the database cannot state live here:

* a picked subject must be one of the enrolled class's subjects — a join across
  ``subject_enrollments`` → ``enrollments`` → ``class_subjects``;
* moving to another class invalidates every pick, because those subjects
  belonged to the old class.

Seats are claimed and released through ``app.services.capacity``, never by
writing ``student_count`` directly. Every subject-set change is applied as a
**diff**, so re-sending an unchanged list touches no counters at all.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import college_now
from app.db.models import (
    Class,
    Enrollment,
    Student,
    Subject,
    SubjectEnrollment,
    class_subjects,
)
from app.exceptions.errors import Conflict, NotFound, Unprocessable
from app.services import capacity
from app.services import classes as classes_service

#: EnrollmentOut renders the class, its program, and every chosen subject. The
#: relationships are all `lazy="raise"`, so they are loaded explicitly here
#: rather than silently emitting an N+1 per list row.
_FULL = (
    selectinload(Enrollment.class_).selectinload(Class.program),
    selectinload(Enrollment.subject_links).selectinload(SubjectEnrollment.subject),
    selectinload(Enrollment.student),
)


async def get_enrollment(db: AsyncSession, enrollment_id: uuid.UUID) -> Enrollment:
    enrollment = await db.scalar(
        select(Enrollment).where(Enrollment.id == enrollment_id).options(*_FULL)
    )
    if enrollment is None:
        raise NotFound("Enrollment not found")
    return enrollment


async def get_by_student(db: AsyncSession, student_id: uuid.UUID) -> Enrollment:
    enrollment = await db.scalar(
        select(Enrollment).where(Enrollment.student_id == student_id).options(*_FULL)
    )
    if enrollment is None:
        raise NotFound("This student is not enrolled in a class")
    return enrollment


async def list_enrollments(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    class_id: uuid.UUID | None = None,
    program_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    q: str | None = None,
) -> tuple[list[Enrollment], int]:
    """The class roster and the subject roster, from one query."""
    filters = []
    if class_id is not None:
        filters.append(Enrollment.class_id == class_id)
    if program_id is not None:
        filters.append(
            Enrollment.class_id.in_(select(Class.id).where(Class.program_id == program_id))
        )
    if subject_id is not None:
        filters.append(
            Enrollment.id.in_(
                select(SubjectEnrollment.enrollment_id).where(
                    SubjectEnrollment.subject_id == subject_id
                )
            )
        )

    student_filters = []
    if session_id is not None:
        student_filters.append(Student.session_id == session_id)
    if q:
        term = f"%{q.strip()}%"
        student_filters.append(
            or_(
                Student.roll_no.ilike(term),
                Student.first_name.ilike(term),
                Student.last_name.ilike(term),
            )
        )
    if student_filters:
        filters.append(Enrollment.student_id.in_(select(Student.id).where(*student_filters)))

    total_query = select(func.count()).select_from(Enrollment)
    list_query = select(Enrollment).options(*_FULL)
    for condition in filters:
        total_query = total_query.where(condition)
        list_query = list_query.where(condition)

    total = await db.scalar(total_query) or 0
    # Ordered by roll number, which is how a roster is read.
    rows = (
        await db.scalars(
            list_query.join(Student, Student.id == Enrollment.student_id)
            .order_by(Student.roll_no)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return list(rows), total


async def _get_student(db: AsyncSession, student_id: uuid.UUID) -> Student:
    student = await db.get(Student, student_id)
    if student is None:
        raise NotFound("Student not found")
    if not student.is_active:
        raise Conflict("This student's record is inactive")
    return student


async def _class_subject_ids(db: AsyncSession, class_id: uuid.UUID) -> set[uuid.UUID]:
    """What this class is allowed to offer."""
    return set(
        (
            await db.scalars(
                select(class_subjects.c.subject_id).where(class_subjects.c.class_id == class_id)
            )
        ).all()
    )


async def _resolve_subjects(
    db: AsyncSession, class_id: uuid.UUID, subject_ids: list[uuid.UUID]
) -> list[Subject]:
    """Load the requested subjects, rejecting any the class does not run.

    Duplicates collapse — the picks are a set, and naming one twice is not
    worth failing over.
    """
    wanted = list(dict.fromkeys(subject_ids))
    if not wanted:
        return []

    subjects = list((await db.scalars(select(Subject).where(Subject.id.in_(wanted)))).all())
    if len(subjects) != len(wanted):
        found = {s.id for s in subjects}
        raise NotFound(
            "Unknown subject",
            details={"subject_ids": [str(i) for i in wanted if i not in found]},
        )

    # 422, not 409: the class simply does not run this subject, so retrying the
    # identical request will never succeed.
    offered = await _class_subject_ids(db, class_id)
    outside = [s for s in subjects if s.id not in offered]
    if outside:
        raise Unprocessable(
            "These subjects are not taught to this class",
            details={
                "subjects": [{"id": str(s.id), "code": s.code} for s in outside],
                "class_id": str(class_id),
            },
        )
    return subjects


async def _apply_subject_diff(
    db: AsyncSession, enrollment: Enrollment, subjects: list[Subject]
) -> None:
    """Move the picks to exactly ``subjects``, touching only what changed."""
    current = {link.subject_id: link for link in enrollment.subject_links}
    wanted = {s.id: s for s in subjects}

    for subject_id in current.keys() - wanted.keys():
        await capacity.release_seat(db, subject_id)
        enrollment.subject_links.remove(current[subject_id])

    for subject_id in wanted.keys() - current.keys():
        subject = wanted[subject_id]
        # Raises 409 if the subject is full — before the link row exists, so a
        # rejected pick leaves nothing behind.
        await capacity.claim_seat(db, subject)
        link = SubjectEnrollment(subject_id=subject_id)
        link.subject = subject
        enrollment.subject_links.append(link)


async def _drop_all_subjects(db: AsyncSession, enrollment: Enrollment) -> int:
    """Release and remove every pick. Returns how many were dropped."""
    dropped = len(enrollment.subject_links)
    for link in list(enrollment.subject_links):
        await capacity.release_seat(db, link.subject_id)
        enrollment.subject_links.remove(link)
    return dropped


async def enroll(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    class_id: uuid.UUID,
    subject_ids: list[uuid.UUID],
) -> Enrollment:
    student = await _get_student(db, student_id)
    if await db.scalar(select(Enrollment.id).where(Enrollment.student_id == student.id)):
        raise Conflict(
            "This student is already enrolled in a class; move them instead",
            details={"student_id": str(student.id)},
        )
    class_ = await classes_service.get_class(db, class_id)

    enrollment = Enrollment(student_id=student.id, class_id=class_.id)
    # The relationships are lazy="raise"; populate them now so the diff below
    # and the caller's response both work without a refetch.
    enrollment.student = student
    enrollment.class_ = class_
    enrollment.subject_links = []
    db.add(enrollment)

    await _apply_subject_diff(db, enrollment, await _resolve_subjects(db, class_.id, subject_ids))
    await db.flush()
    return enrollment


async def move_class(
    db: AsyncSession, enrollment_id: uuid.UUID, class_id: uuid.UUID
) -> tuple[Enrollment, int]:
    """Move a student to another class. Returns the enrollment and picks dropped.

    Every subject they had chosen belonged to the old class, so the move drops
    all of them and releases their seats. The count comes back so the caller
    can say so rather than leaving it to be discovered.
    """
    enrollment = await get_enrollment(db, enrollment_id)
    if enrollment.class_id == class_id:
        return enrollment, 0

    class_ = await classes_service.get_class(db, class_id)
    dropped = await _drop_all_subjects(db, enrollment)

    enrollment.class_id = class_.id
    enrollment.class_ = class_
    # The app's clock, not the database's — the same rule as the column default.
    enrollment.enrolled_at = college_now()
    await db.flush()
    return enrollment, dropped


async def set_subjects(
    db: AsyncSession, enrollment_id: uuid.UUID, subject_ids: list[uuid.UUID]
) -> Enrollment:
    """Replace the chosen subjects. An empty list is valid and means "none"."""
    enrollment = await get_enrollment(db, enrollment_id)
    subjects = await _resolve_subjects(db, enrollment.class_id, subject_ids)
    await _apply_subject_diff(db, enrollment, subjects)
    await db.flush()
    return enrollment


async def unenroll(db: AsyncSession, enrollment_id: uuid.UUID) -> None:
    enrollment = await get_enrollment(db, enrollment_id)
    await _drop_all_subjects(db, enrollment)
    await db.delete(enrollment)
    await db.flush()


async def count_in_class(db: AsyncSession, class_id: uuid.UUID) -> int:
    """Students enrolled in a class. Guards the class's deletion."""
    return (
        await db.scalar(
            select(func.count()).select_from(Enrollment).where(Enrollment.class_id == class_id)
        )
        or 0
    )
