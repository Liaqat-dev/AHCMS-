"""Students router (staff-facing).

Managed by staff under ``students:read`` / ``students:write``. Students
themselves never reach these endpoints — their own surface is the portal in
``app.api.v1.student_portal``.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DBSession, Pagination, require_permissions
from app.api.v1.attendance import student_report
from app.core import permissions as perm
from app.schemas.attendance import StudentAttendanceOut
from app.schemas.common import Page
from app.schemas.enrollment import EnrollmentOut
from app.schemas.student import (
    StudentCreate,
    StudentOut,
    StudentPasswordReset,
    StudentUpdate,
)
from app.services import enrollments as enrollments_service
from app.services import students as students_service

router = APIRouter(prefix="/students", tags=["students"])


@router.post(
    "",
    response_model=StudentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(perm.STUDENTS_CREATE))],
)
async def create_student(body: StudentCreate, db: DBSession) -> StudentOut:
    payload = body.model_dump()
    student = await students_service.create_student(
        db,
        session_id=payload.pop("session_id"),
        first_name=payload.pop("first_name"),
        last_name=payload.pop("last_name"),
        password=payload.pop("password"),
        **payload,
    )
    await db.commit()
    return StudentOut.from_student(student)


@router.get(
    "",
    response_model=Page[StudentOut],
    dependencies=[Depends(require_permissions(perm.STUDENTS_READ))],
)
async def list_students(
    pagination: Pagination,
    db: DBSession,
    session_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100, description="Roll no, name or CNIC")] = None,
) -> Page[StudentOut]:
    students, total = await students_service.list_students(
        db,
        limit=pagination.limit,
        offset=pagination.offset,
        session_id=session_id,
        q=q,
    )
    return Page(
        items=[StudentOut.from_student(s) for s in students],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/{student_id}",
    response_model=StudentOut,
    dependencies=[Depends(require_permissions(perm.STUDENTS_READ))],
)
async def get_student(student_id: uuid.UUID, db: DBSession) -> StudentOut:
    return StudentOut.from_student(await students_service.get_student(db, student_id))


@router.get(
    "/{student_id}/enrollment",
    response_model=EnrollmentOut,
    dependencies=[Depends(require_permissions(perm.ENROLLMENTS_READ))],
)
async def get_student_enrollment(student_id: uuid.UUID, db: DBSession) -> EnrollmentOut:
    """The student's class and subjects, addressed by student rather than by
    enrollment id. 404 when they have not been enrolled yet."""
    return EnrollmentOut.from_enrollment(await enrollments_service.get_by_student(db, student_id))


@router.get(
    "/{student_id}/attendance",
    response_model=StudentAttendanceOut,
    dependencies=[Depends(require_permissions(perm.ATTENDANCE_READ))],
)
async def get_student_attendance(
    student_id: uuid.UUID,
    pagination: Pagination,
    db: DBSession,
    date_from: Annotated[date_type | None, Query(description="Inclusive")] = None,
    date_to: Annotated[date_type | None, Query(description="Inclusive")] = None,
) -> StudentAttendanceOut:
    """One student's register history and their percentage.

    Counted from their enrolment day: a student who joined in March is not
    measured against February.
    """
    return await student_report(
        db, student_id, pagination=pagination, date_from=date_from, date_to=date_to
    )


@router.patch(
    "/{student_id}",
    response_model=StudentOut,
    dependencies=[Depends(require_permissions(perm.STUDENTS_UPDATE))],
)
async def update_student(student_id: uuid.UUID, body: StudentUpdate, db: DBSession) -> StudentOut:
    # exclude_unset so an omitted field stays as it is, rather than being
    # nulled out by the schema's default.
    student = await students_service.update_student(
        db, student_id, body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return StudentOut.from_student(student)


@router.put(
    "/{student_id}/password",
    response_model=StudentOut,
    dependencies=[Depends(require_permissions(perm.STUDENTS_UPDATE))],
)
async def reset_student_password(
    student_id: uuid.UUID, body: StudentPasswordReset, db: DBSession
) -> StudentOut:
    student = await students_service.set_password(db, student_id, body.password)
    await db.commit()
    return StudentOut.from_student(student)
