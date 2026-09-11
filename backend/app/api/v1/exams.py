"""Exams router — papers sat by a class, and the marks recorded against them.

Scheduling is open to teachers as well as administrators: ``exams:create``
ships with the ``teacher`` role, because setting a paper is teaching work.

**Marks are the one place in this API where a permission is not the whole
answer.** ``marks:update`` lets you enter marks for the subjects *you teach* —
the subject names a ``Faculty`` row, and a staff account is recognised as that
person through ``faculty.user_id``. ``marks:update_any`` is the office's
override, for a paper whose teacher has left. See
``services.exams.assert_may_mark``.

Unlike an attendance register, an exam may be dated in the future: announcing
one before it happens is the point.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import AuthContext, CurrentUser, DBSession, Pagination, require_permissions
from app.core import permissions as perm
from app.schemas.common import Page
from app.schemas.exam import (
    ExamCreate,
    ExamOut,
    ExamUpdate,
    MarkBatch,
    MarkOut,
    MarkSheet,
    PaperOut,
    PaperTotalUpdate,
    StudentRef,
)
from app.services import exams as exams_service

router = APIRouter(prefix="/exams", tags=["exams"])

_ReadDep = Depends(require_permissions(perm.EXAMS_READ))
_MarksReadDep = Depends(require_permissions(perm.MARKS_READ))


@router.post("", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
async def create_exam(
    body: ExamCreate,
    db: DBSession,
    auth: Annotated[AuthContext, Depends(require_permissions(perm.EXAMS_CREATE))],
) -> ExamOut:
    """Schedule an exam over one subject or over everything the class runs.

    The subjects it covers are written down now: a class's subject list
    changes, and an exam is a record of the papers that were actually set.
    """
    exam = await exams_service.create_exam(
        db,
        class_id=body.class_id,
        title=body.title,
        on=body.date,
        scope=body.scope,
        subject_id=body.subject_id,
        total_marks=body.total_marks,
        created_by_id=auth.user.id,
    )
    await db.commit()
    return ExamOut.from_exam(exam, await exams_service.mark_counts(db, [exam]))


@router.get("", response_model=Page[ExamOut], dependencies=[_ReadDep])
async def list_exams(
    pagination: Pagination,
    db: DBSession,
    class_id: uuid.UUID | None = None,
    subject_id: Annotated[
        uuid.UUID | None, Query(description="Exams that include this subject")
    ] = None,
    q: Annotated[str | None, Query(max_length=100, description="Title")] = None,
) -> Page[ExamOut]:
    exams, total = await exams_service.list_exams(
        db,
        limit=pagination.limit,
        offset=pagination.offset,
        class_id=class_id,
        subject_id=subject_id,
        q=q,
    )
    counts = await exams_service.mark_counts(db, exams)
    return Page(
        items=[ExamOut.from_exam(e, counts) for e in exams],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{exam_id}", response_model=ExamOut, dependencies=[_ReadDep])
async def get_exam(exam_id: uuid.UUID, db: DBSession) -> ExamOut:
    exam = await exams_service.get_exam(db, exam_id)
    return ExamOut.from_exam(exam, await exams_service.mark_counts(db, [exam]))


@router.patch(
    "/{exam_id}",
    response_model=ExamOut,
    dependencies=[Depends(require_permissions(perm.EXAMS_UPDATE))],
)
async def update_exam(exam_id: uuid.UUID, body: ExamUpdate, db: DBSession) -> ExamOut:
    """Rename or move an exam. Which papers it consists of is fixed."""
    exam = await exams_service.update_exam(
        db, exam_id, body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return ExamOut.from_exam(exam, await exams_service.mark_counts(db, [exam]))


@router.delete(
    "/{exam_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(perm.EXAMS_DELETE))],
)
async def delete_exam(exam_id: uuid.UUID, db: DBSession) -> None:
    """Delete an exam and every mark recorded against it."""
    await exams_service.delete_exam(db, exam_id)
    await db.commit()


@router.patch(
    "/papers/{paper_id}",
    response_model=PaperOut,
    dependencies=[Depends(require_permissions(perm.EXAMS_UPDATE))],
)
async def update_paper(
    paper_id: uuid.UUID, body: PaperTotalUpdate, db: DBSession
) -> PaperOut:
    """Change one paper's total. Refused if a mark already exceeds it."""
    paper = await exams_service.set_paper_total(db, paper_id, body.total_marks)
    await db.commit()
    return PaperOut.from_paper(paper, len(paper.marks))


@router.get("/papers/{paper_id}/marks", response_model=MarkSheet, dependencies=[_MarksReadDep])
async def get_marks(paper_id: uuid.UUID, db: DBSession, auth: CurrentUser) -> MarkSheet:
    """The mark sheet: everyone sitting this paper, with what they scored.

    ``can_mark`` says whether *this* caller may edit it, so the client can show
    a read-only sheet rather than letting somebody type into a form that will
    be refused.
    """
    paper = await exams_service.get_exam_subject(db, paper_id)
    return await _sheet(db, paper, auth)


@router.put("/papers/{paper_id}/marks", response_model=MarkSheet, dependencies=[_MarksReadDep])
async def set_marks(
    paper_id: uuid.UUID, body: MarkBatch, db: DBSession, auth: CurrentUser
) -> MarkSheet:
    """Record marks for the students named; others are left as they are.

    Refused unless the caller teaches this subject, or holds the override.
    """
    paper = await exams_service.get_exam_subject(db, paper_id)
    await exams_service.assert_may_mark(db, auth, paper)

    paper = await exams_service.set_marks(
        db, paper, [m.model_dump() for m in body.marks], marked_by_id=auth.user.id
    )
    await db.commit()
    return await _sheet(db, paper, auth)


async def _sheet(db: DBSession, paper, auth: AuthContext) -> MarkSheet:
    roster = await exams_service.paper_roster(db, paper)
    recorded = {mark.student_id: mark for mark in paper.marks}

    try:
        await exams_service.assert_may_mark(db, auth, paper)
        can_mark = True
    except Exception:  # noqa: BLE001 - the reason is the client's, not ours
        can_mark = False

    return MarkSheet(
        paper=PaperOut.from_paper(paper, len(paper.marks)),
        exam_id=paper.exam_id,
        exam_title=paper.exam.title,
        date=paper.exam.date,
        class_name=paper.exam.class_.name,
        can_mark=can_mark,
        marks=[
            MarkOut(
                student=StudentRef.model_validate(student),
                obtained=recorded[student.id].obtained if student.id in recorded else None,
                is_absent=recorded[student.id].is_absent if student.id in recorded else False,
                marked_by_id=recorded[student.id].marked_by_id if student.id in recorded else None,
                marked_at=recorded[student.id].marked_at if student.id in recorded else None,
            )
            for student in roster
        ],
    )
