"""Enrollments router — the one class a student is in, and their subjects.

A student enrolls in exactly one class (``UNIQUE(student_id)`` in the
database), and takes any subset of that class's subjects, including none.
Subjects are shared across programs on purpose: a Medical and an Engineering
class can both run the same English, and differ only where Maths and Biology
diverge.

Staff-only. Students read their own enrollment through the portal
(``GET /api/v1/student/me/enrollment``) but never write it — choosing subjects
is a recorded decision, not a self-service one.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DBSession, Pagination, require_permissions
from app.core import permissions as perm
from app.schemas.common import Page
from app.schemas.enrollment import (
    EnrollmentCreate,
    EnrollmentMove,
    EnrollmentMoveOut,
    EnrollmentOut,
    SubjectSelection,
)
from app.services import enrollments as enrollments_service

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


@router.post(
    "",
    response_model=EnrollmentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(perm.ENROLLMENTS_CREATE))],
)
async def create_enrollment(body: EnrollmentCreate, db: DBSession) -> EnrollmentOut:
    """Enrol a student in a class, optionally with their subjects in one call."""
    enrollment = await enrollments_service.enroll(
        db,
        student_id=body.student_id,
        class_id=body.class_id,
        subject_ids=body.subject_ids,
    )
    await db.commit()
    return EnrollmentOut.from_enrollment(enrollment)


@router.get(
    "",
    response_model=Page[EnrollmentOut],
    dependencies=[Depends(require_permissions(perm.ENROLLMENTS_READ))],
)
async def list_enrollments(
    pagination: Pagination,
    db: DBSession,
    class_id: Annotated[uuid.UUID | None, Query(description="Class roster")] = None,
    program_id: Annotated[uuid.UUID | None, Query(description="All of a program")] = None,
    session_id: Annotated[uuid.UUID | None, Query(description="One intake batch")] = None,
    subject_id: Annotated[uuid.UUID | None, Query(description="Subject roster")] = None,
    q: Annotated[str | None, Query(max_length=100, description="Roll no or name")] = None,
) -> Page[EnrollmentOut]:
    enrollments, total = await enrollments_service.list_enrollments(
        db,
        limit=pagination.limit,
        offset=pagination.offset,
        class_id=class_id,
        program_id=program_id,
        session_id=session_id,
        subject_id=subject_id,
        q=q,
    )
    return Page(
        items=[EnrollmentOut.from_enrollment(e) for e in enrollments],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/{enrollment_id}",
    response_model=EnrollmentOut,
    dependencies=[Depends(require_permissions(perm.ENROLLMENTS_READ))],
)
async def get_enrollment(enrollment_id: uuid.UUID, db: DBSession) -> EnrollmentOut:
    return EnrollmentOut.from_enrollment(
        await enrollments_service.get_enrollment(db, enrollment_id)
    )


@router.patch(
    "/{enrollment_id}",
    response_model=EnrollmentMoveOut,
    dependencies=[Depends(require_permissions(perm.ENROLLMENTS_UPDATE))],
)
async def move_enrollment(
    enrollment_id: uuid.UUID, body: EnrollmentMove, db: DBSession
) -> EnrollmentMoveOut:
    """Move the student to another class.

    Their existing subjects belong to the old class, so all of them are
    dropped and their seats released. The response says how many, rather than
    leaving that to be discovered.
    """
    enrollment, dropped = await enrollments_service.move_class(db, enrollment_id, body.class_id)
    await db.commit()
    return EnrollmentMoveOut(
        enrollment=EnrollmentOut.from_enrollment(enrollment), dropped_subjects=dropped
    )


@router.put(
    "/{enrollment_id}/subjects",
    response_model=EnrollmentOut,
    dependencies=[Depends(require_permissions(perm.ENROLLMENTS_UPDATE))],
)
async def set_enrollment_subjects(
    enrollment_id: uuid.UUID, body: SubjectSelection, db: DBSession
) -> EnrollmentOut:
    """Replace the subjects this student takes. An empty list means none."""
    enrollment = await enrollments_service.set_subjects(db, enrollment_id, body.subject_ids)
    await db.commit()
    return EnrollmentOut.from_enrollment(enrollment)


@router.delete(
    "/{enrollment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(perm.ENROLLMENTS_DELETE))],
)
async def delete_enrollment(enrollment_id: uuid.UUID, db: DBSession) -> None:
    """Unenroll. The subject picks go with it and their seats are released."""
    await enrollments_service.unenroll(db, enrollment_id)
    await db.commit()
