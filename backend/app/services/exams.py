"""Exams and the marks recorded against them.

Two rules the database cannot state live here:

* an exam's subjects are the ones its class ran **when it was scheduled**, so a
  class-wide exam materializes that list at creation rather than deriving it
  later;
* **only the teacher of a subject may enter its marks** — the first
  ownership rule in this app. Everything else is settled by a permission code
  alone; this one also asks *who you are*, by joining the signed-in ``User`` to
  a ``Faculty`` row through ``faculty.user_id`` and comparing that to
  ``subjects.teacher_id``. ``marks:update_any`` lifts the restriction.

A student's mark row exists only once somebody records something: no row means
"not entered", which is different from a zero.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import AuthContext
from app.core import permissions as perm
from app.core.clock import college_now
from app.db.models import (
    Class,
    Enrollment,
    Exam,
    ExamMark,
    ExamSubject,
    Faculty,
    Student,
    Subject,
    SubjectEnrollment,
    class_subjects,
)
from app.db.models.exam import DEFAULT_TOTAL_MARKS, SCOPE_CLASS, SCOPE_SUBJECT
from app.exceptions.errors import BadRequest, Conflict, Forbidden, NotFound, Unprocessable

#: Everything an exam response renders. All relationships are lazy="raise".
_FULL = (
    selectinload(Exam.class_).selectinload(Class.program),
    selectinload(Exam.subjects).selectinload(ExamSubject.subject).selectinload(Subject.teacher),
)

#: Columns a PATCH may set. The class and the scope are not among them: they
#: decide which papers exist, and changing them would orphan marks.
UPDATABLE_FIELDS = frozenset({"title", "date"})


# --------------------------------------------------------------------- reads
async def get_exam(db: AsyncSession, exam_id: uuid.UUID) -> Exam:
    exam = await db.scalar(select(Exam).where(Exam.id == exam_id).options(*_FULL))
    if exam is None:
        raise NotFound("Exam not found")
    return exam


async def list_exams(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    class_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    q: str | None = None,
) -> tuple[list[Exam], int]:
    filters = []
    if class_id is not None:
        filters.append(Exam.class_id == class_id)
    if subject_id is not None:
        filters.append(
            Exam.id.in_(
                select(ExamSubject.exam_id).where(ExamSubject.subject_id == subject_id)
            )
        )
    if q:
        filters.append(Exam.title.ilike(f"%{q.strip()}%"))

    total_query = select(func.count()).select_from(Exam)
    list_query = select(Exam).options(*_FULL)
    for condition in filters:
        total_query = total_query.where(condition)
        list_query = list_query.where(condition)

    total = await db.scalar(total_query) or 0
    # Newest sitting first: the exam you are marking is the one just gone.
    exams = (
        await db.scalars(
            list_query.order_by(Exam.date.desc(), Exam.title).limit(limit).offset(offset)
        )
    ).all()
    return list(exams), total


async def mark_counts(db: AsyncSession, exams: list[Exam]) -> dict[uuid.UUID, int]:
    """How many marks are recorded on each paper of these exams.

    One grouped query rather than loading every mark row to call ``len`` on it:
    a list of twenty exams would otherwise pull a few thousand marks in order
    to print twenty numbers.
    """
    paper_ids = [paper.id for exam in exams for paper in exam.subjects]
    if not paper_ids:
        return {}
    rows = (
        await db.execute(
            select(ExamMark.exam_subject_id, func.count())
            .where(ExamMark.exam_subject_id.in_(paper_ids))
            .group_by(ExamMark.exam_subject_id)
        )
    ).all()
    return dict(rows)  # type: ignore[arg-type]


async def get_exam_subject(db: AsyncSession, exam_subject_id: uuid.UUID) -> ExamSubject:
    paper = await db.scalar(
        select(ExamSubject)
        .where(ExamSubject.id == exam_subject_id)
        .options(
            selectinload(ExamSubject.subject).selectinload(Subject.teacher),
            selectinload(ExamSubject.exam).selectinload(Exam.class_),
            selectinload(ExamSubject.marks),
        )
    )
    if paper is None:
        raise NotFound("This exam does not cover that subject")
    return paper


async def paper_roster(db: AsyncSession, paper: ExamSubject) -> list[Student]:
    """Who sits this paper: the students who took the subject up, by roll number.

    Drawn from ``subject_enrollments`` rather than the class, because subjects
    are optional — a class-wide exam still only examines each student in the
    subjects they actually chose.
    """
    return list(
        (
            await db.scalars(
                select(Student)
                .join(Enrollment, Enrollment.student_id == Student.id)
                .join(SubjectEnrollment, SubjectEnrollment.enrollment_id == Enrollment.id)
                .where(SubjectEnrollment.subject_id == paper.subject_id)
                .order_by(Student.roll_no)
            )
        ).all()
    )


# ---------------------------------------------------------------- ownership
async def faculty_for(db: AsyncSession, user_id: uuid.UUID) -> Faculty | None:
    """The personnel record this login belongs to, if it has been linked."""
    return await db.scalar(select(Faculty).where(Faculty.user_id == user_id))


async def assert_may_mark(db: AsyncSession, auth: AuthContext, paper: ExamSubject) -> None:
    """Only the subject's teacher may enter its marks.

    ``marks:update_any`` is the office's override. Otherwise the caller must
    hold ``marks:update`` *and* be the faculty member the subject names — which
    requires their staff account to be linked to a personnel record. Saying so
    explicitly matters: "you are not the teacher" and "nobody has linked your
    account to your staff file" are different problems with different fixes.
    """
    if perm.MARKS_UPDATE_ANY in auth.permissions:
        return
    if perm.MARKS_UPDATE not in auth.permissions:
        raise Forbidden(details={"missing_permissions": [perm.MARKS_UPDATE]})

    if paper.subject.teacher_id is None:
        raise Forbidden(
            f"{paper.subject.name} has no teacher assigned, so only someone with "
            "marks:update_any can enter its marks"
        )

    member = await faculty_for(db, auth.user.id)
    if member is None:
        raise Forbidden(
            "This account is not linked to a faculty record, so it cannot be "
            "recognised as a subject's teacher"
        )
    if member.id != paper.subject.teacher_id:
        raise Forbidden(f"{paper.subject.name} is taught by somebody else")


# -------------------------------------------------------------------- writes
async def _class_subject_ids(db: AsyncSession, class_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        (
            await db.scalars(
                select(class_subjects.c.subject_id).where(
                    class_subjects.c.class_id == class_id
                )
            )
        ).all()
    )


async def create_exam(
    db: AsyncSession,
    *,
    class_id: uuid.UUID,
    title: str,
    on: date_type,
    scope: str,
    subject_id: uuid.UUID | None,
    total_marks: int,
    created_by_id: uuid.UUID | None,
) -> Exam:
    """Schedule an exam over one subject or over everything the class runs.

    The subject list is written down now. A class's subjects change; the papers
    an exam consisted of do not.
    """
    class_ = await db.get(Class, class_id)
    if class_ is None:
        raise NotFound("Class not found")

    if scope == SCOPE_SUBJECT:
        if subject_id is None:
            raise BadRequest("A single-subject exam needs a subject")
        offered = await _class_subject_ids(db, class_id)
        if subject_id not in offered:
            # 422, not 409: this class does not run that subject, and retrying
            # the identical request will never succeed.
            raise Unprocessable(
                "That subject is not taught to this class",
                details={"subject_id": str(subject_id), "class_id": str(class_id)},
            )
        subject_ids = [subject_id]
    else:
        subject_ids = await _class_subject_ids(db, class_id)
        if not subject_ids:
            raise Conflict(
                f"{class_.name} runs no subjects, so there is nothing to examine",
                details={"class_id": str(class_id)},
            )

    exam = Exam(
        class_id=class_.id,
        title=title,
        date=on,
        scope=scope,
        created_by_id=created_by_id,
        subjects=[
            ExamSubject(subject_id=sid, total_marks=total_marks) for sid in subject_ids
        ],
    )
    db.add(exam)
    await db.flush()
    return await get_exam(db, exam.id)


async def update_exam(db: AsyncSession, exam_id: uuid.UUID, changes: dict) -> Exam:
    """Rename or move an exam. Its papers are fixed once it is scheduled."""
    unknown = set(changes) - UPDATABLE_FIELDS
    if unknown:
        raise BadRequest("Unknown fields", details={"fields": sorted(unknown)})

    exam = await get_exam(db, exam_id)
    for field, value in changes.items():
        setattr(exam, field, value)
    await db.flush()
    db.expire(exam)
    return await get_exam(db, exam_id)


async def set_paper_total(
    db: AsyncSession, exam_subject_id: uuid.UUID, total_marks: int
) -> ExamSubject:
    """Change one paper's total.

    Refused once it would invalidate a mark already entered: a 40 out of 50 does
    not silently become 40 out of 30.
    """
    paper = await get_exam_subject(db, exam_subject_id)
    highest = await db.scalar(
        select(func.max(ExamMark.obtained)).where(ExamMark.exam_subject_id == paper.id)
    )
    if highest is not None and total_marks < highest:
        raise Conflict(
            "A mark already entered is higher than that total",
            details={"total_marks": total_marks, "highest_entered": highest},
        )

    paper.total_marks = total_marks
    await db.flush()
    return paper


async def delete_exam(db: AsyncSession, exam_id: uuid.UUID) -> None:
    """Delete an exam and everything recorded against it."""
    exam = await get_exam(db, exam_id)
    await db.delete(exam)
    await db.flush()


async def set_marks(
    db: AsyncSession,
    paper: ExamSubject,
    entries: list[dict],
    *,
    marked_by_id: uuid.UUID | None,
) -> ExamSubject:
    """Record marks for the students named. Others are left alone.

    ``obtained: null`` with ``is_absent`` false clears the mark back to "not
    entered", which is the only way back to it.
    """
    eligible = {student.id for student in await paper_roster(db, paper)}
    by_student = {entry["student_id"]: entry for entry in entries}

    outside = sorted(str(sid) for sid in by_student.keys() - eligible)
    if outside:
        raise Unprocessable(
            "These students are not taking this subject",
            details={"student_ids": outside, "subject": paper.subject.code},
        )

    over = sorted(
        str(sid)
        for sid, entry in by_student.items()
        if entry.get("obtained") is not None and entry["obtained"] > paper.total_marks
    )
    if over:
        raise Unprocessable(
            f"A mark is higher than the paper's total of {paper.total_marks}",
            details={"student_ids": over, "total_marks": paper.total_marks},
        )

    existing = {mark.student_id: mark for mark in paper.marks}
    now = college_now()

    for student_id, entry in by_student.items():
        absent = bool(entry.get("is_absent"))
        obtained = None if absent else entry.get("obtained")
        mark = existing.get(student_id)

        if obtained is None and not absent:
            # Back to "not entered".
            if mark is not None:
                paper.marks.remove(mark)
            continue

        if mark is None:
            mark = ExamMark(exam_subject_id=paper.id, student_id=student_id)
            paper.marks.append(mark)
        mark.obtained = obtained
        mark.is_absent = absent
        mark.marked_by_id = marked_by_id
        mark.marked_at = now

    await db.flush()
    return await get_exam_subject(db, paper.id)


async def count_for_subject(db: AsyncSession, subject_id: uuid.UUID) -> int:
    """Papers set on a subject. Guards the subject's deletion."""
    return (
        await db.scalar(
            select(func.count())
            .select_from(ExamSubject)
            .where(ExamSubject.subject_id == subject_id)
        )
        or 0
    )


async def count_for_class(db: AsyncSession, class_id: uuid.UUID) -> int:
    """Exams sat by a class. Guards the class's deletion."""
    return (
        await db.scalar(select(func.count()).select_from(Exam).where(Exam.class_id == class_id))
        or 0
    )


__all__ = [
    "DEFAULT_TOTAL_MARKS",
    "SCOPE_CLASS",
    "SCOPE_SUBJECT",
    "assert_may_mark",
    "count_for_class",
    "count_for_subject",
    "create_exam",
    "delete_exam",
    "faculty_for",
    "get_exam",
    "get_exam_subject",
    "list_exams",
    "paper_roster",
    "set_marks",
    "set_paper_total",
    "update_exam",
]