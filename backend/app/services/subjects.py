"""Subjects — taught subjects, shared across classes.

Reading is granted to teachers by default; everything else needs
``subjects:write``, which is seeded only to ``super_admin``.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Class,
    Enrollment,
    ExamSubject,
    Faculty,
    Subject,
    SubjectEnrollment,
    class_subjects,
)
from app.exceptions.errors import BadRequest, Conflict, NotFound

#: Columns a PATCH may set. The class list is not among them: it has its own
#: endpoint, because replacing a collection and patching a scalar are different
#: operations to reason about.
# student_count is absent on purpose: it is a cache of the subject_enrollments
# rows and only app.services.capacity writes it.
UPDATABLE_FIELDS = frozenset({"name", "code", "student_limit", "teacher_id"})


async def get_subject(db: AsyncSession, subject_id: uuid.UUID) -> Subject:
    # Subject.classes is lazy="selectin", so it is loaded with the row.
    subject = await db.scalar(select(Subject).where(Subject.id == subject_id))
    if subject is None:
        raise NotFound("Subject not found")
    return subject


async def list_subjects(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    class_id: uuid.UUID | None = None,
    q: str | None = None,
) -> tuple[list[Subject], int]:
    total_query = select(func.count()).select_from(Subject)
    list_query = select(Subject)

    if class_id is not None:
        # A subject belongs to many classes, so filter through the join table
        # rather than joining the rows (which would multiply them).
        in_class = select(class_subjects.c.subject_id).where(class_subjects.c.class_id == class_id)
        total_query = total_query.where(Subject.id.in_(in_class))
        list_query = list_query.where(Subject.id.in_(in_class))
    if q:
        term = f"%{q.strip()}%"
        condition = or_(Subject.name.ilike(term), Subject.code.ilike(term))
        total_query = total_query.where(condition)
        list_query = list_query.where(condition)

    total = await db.scalar(total_query) or 0
    subjects = (
        await db.scalars(list_query.order_by(Subject.name).limit(limit).offset(offset))
    ).all()
    return list(subjects), total


async def _assert_unique(
    db: AsyncSession,
    *,
    name: str | None = None,
    code: str | None = None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """Guard both unique columns with a clear 409 instead of an IntegrityError."""
    for column, value, label in (
        (Subject.name, name, "name"),
        (Subject.code, code, "code"),
    ):
        if value is None:
            continue
        query = select(Subject.id).where(func.lower(column) == value.lower())
        if exclude_id is not None:
            query = query.where(Subject.id != exclude_id)
        if await db.scalar(query):
            raise Conflict(f"A subject with this {label} already exists")


def _assert_limit_fits(subject: Subject, student_limit: int) -> None:
    """A subject cannot be shrunk below the students already taking it."""
    if student_limit < subject.student_count:
        raise Conflict(
            "Student limit cannot be lower than the students already enrolled",
            details={
                "student_limit": student_limit,
                "student_count": subject.student_count,
            },
        )


async def _count_enrolled(db: AsyncSession, subject_id: uuid.UUID) -> int:
    """Students who have taken this subject up, counted from the rows.

    Read straight from ``subject_enrollments`` rather than trusting
    ``student_count``: this backs the refusals below, so it should not depend on
    the cache being right.
    """
    return (
        await db.scalar(
            select(func.count())
            .select_from(SubjectEnrollment)
            .where(SubjectEnrollment.subject_id == subject_id)
        )
        or 0
    )


async def _resolve_classes(db: AsyncSession, class_ids: list[uuid.UUID]) -> list[Class]:
    """Load the named classes, rejecting ids that do not exist.

    Duplicates in the request are collapsed — the link table is a set, and
    listing a class twice is not an error worth failing over.
    """
    wanted = list(dict.fromkeys(class_ids))
    if not wanted:
        return []

    classes = list((await db.scalars(select(Class).where(Class.id.in_(wanted)))).all())
    if len(classes) != len(wanted):
        found = {c.id for c in classes}
        raise NotFound(
            "Unknown class", details={"class_ids": [str(i) for i in wanted if i not in found]}
        )
    return classes


async def _assert_teacher(db: AsyncSession, teacher_id: uuid.UUID | None) -> None:
    """404 on an unknown teacher rather than a foreign key violation."""
    if teacher_id is None:
        return
    if not await db.scalar(select(Faculty.id).where(Faculty.id == teacher_id)):
        raise NotFound("Faculty member not found", details={"teacher_id": str(teacher_id)})


async def create_subject(
    db: AsyncSession,
    *,
    name: str,
    code: str,
    student_limit: int,
    teacher_id: uuid.UUID | None,
    class_ids: list[uuid.UUID],
) -> Subject:
    await _assert_unique(db, name=name, code=code)
    await _assert_teacher(db, teacher_id)

    subject = Subject(
        name=name,
        code=code,
        student_limit=student_limit,
        teacher_id=teacher_id,
        classes=await _resolve_classes(db, class_ids),
    )
    db.add(subject)
    await db.flush()
    # Refetched so `teacher` is loaded: only the foreign key was set, and the
    # relationship on a freshly added row is otherwise unloaded — the caller
    # would render "unassigned" for a subject that has a teacher.
    return await get_subject(db, subject.id)


async def update_subject(
    db: AsyncSession, subject_id: uuid.UUID, changes: dict[str, Any]
) -> Subject:
    """Apply a partial update.

    ``changes`` must come from ``model_dump(exclude_unset=True)`` — an omitted
    field has to stay untouched, not be overwritten with the schema's ``None``
    default.
    """
    unknown = set(changes) - UPDATABLE_FIELDS
    if unknown:
        raise BadRequest("Unknown fields", details={"fields": sorted(unknown)})

    subject = await get_subject(db, subject_id)
    await _assert_unique(
        db, name=changes.get("name"), code=changes.get("code"), exclude_id=subject.id
    )
    if "student_limit" in changes:
        _assert_limit_fits(subject, changes["student_limit"])
    if "teacher_id" in changes:
        await _assert_teacher(db, changes["teacher_id"])

    for field, value in changes.items():
        setattr(subject, field, value)
    await db.flush()
    # Expire before refetching. `teacher` still holds whoever it was before the
    # foreign key changed, and a plain re-query will not overwrite an attribute
    # the identity map already has loaded — so a cleared assignment would come
    # back still naming them, and a new one would come back as unassigned.
    # `subject_id` rather than `subject.id`: expire() unloads every attribute,
    # so reading the id back off the instance would itself be a lazy database
    # read — synchronous, and therefore an error under asyncio.
    db.expire(subject)
    return await get_subject(db, subject_id)


async def set_classes(
    db: AsyncSession, subject_id: uuid.UUID, class_ids: list[uuid.UUID]
) -> Subject:
    """Replace the set of classes this subject is taught to.

    Detaching a class whose students have already taken this subject up is
    refused: their choice would become invalid as a side effect of an edit
    aimed at something else, and nobody would notice until results are
    compiled. Unenroll them first.
    """
    subject = await get_subject(db, subject_id)
    wanted = await _resolve_classes(db, class_ids)

    dropped = {c.id for c in subject.classes} - {c.id for c in wanted}
    if dropped:
        # Enrollment is per class, so this counts students of the dropped
        # classes who hold this subject.
        blocked = (
            await db.execute(
                select(Class.id, Class.name, func.count(SubjectEnrollment.id))
                .join(Enrollment, Enrollment.class_id == Class.id)
                .join(
                    SubjectEnrollment,
                    (SubjectEnrollment.enrollment_id == Enrollment.id)
                    & (SubjectEnrollment.subject_id == subject.id),
                )
                .where(Class.id.in_(dropped))
                .group_by(Class.id, Class.name)
            )
        ).all()
        if blocked:
            raise Conflict(
                "Students in these classes have already taken this subject",
                details={
                    "classes": [
                        {"id": str(cid), "name": name, "students": count}
                        for cid, name, count in blocked
                    ]
                },
            )

    subject.classes = wanted
    await db.flush()
    return subject


async def delete_subject(db: AsyncSession, subject_id: uuid.UUID) -> None:
    subject = await get_subject(db, subject_id)

    # subject_enrollments is ON DELETE RESTRICT, so this would otherwise be an
    # IntegrityError (a 500) at flush time. Say what is actually in the way.
    enrolled = await _count_enrolled(db, subject.id)
    if enrolled:
        raise Conflict(
            f"{enrolled} student(s) have taken this subject; unenroll them first",
            details={"student_count": enrolled},
        )

    # Exam papers are ON DELETE RESTRICT for the same reason: deleting the
    # subject would take the marks recorded against it.
    papers = (
        await db.scalar(
            select(func.count())
            .select_from(ExamSubject)
            .where(ExamSubject.subject_id == subject.id)
        )
        or 0
    )
    if papers:
        raise Conflict(
            f"{papers} exam paper(s) have been set on this subject; delete those exams first",
            details={"exam_papers": papers},
        )

    # The class links go with it: class_subjects is ON DELETE CASCADE, and the
    # relationship's secondary rows are cleared by the ORM on delete.
    await db.delete(subject)
    await db.flush()
