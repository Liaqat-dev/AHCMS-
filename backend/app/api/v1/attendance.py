"""Attendance router — one register per class per calendar day.

Opening and marking are open to any staff member holding ``attendance:create``
and ``attendance:update``, which ship with the ``teacher`` role as well as
``super_admin``: taking the register is a teacher's daily job, not an
administrative act. ``attendance:delete`` does not ship with it — deleting a
register throws away a day's marks for a whole class. There is no ownership — anyone
may mark any class. It is still a permission rather than "any staff account",
so it can be narrowed later without touching the schema.

Every mark records who set it and when. Sheets stay editable indefinitely;
the author trail is what makes that safe to revisit.

Dates are the college's, not the server's: omit ``date`` and you get today in
``COLLEGE_TIMEZONE``, so a register opened at 1am in Karachi is not filed under
yesterday by a UTC host.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AuthContext,
    DBSession,
    Pagination,
    PaginationParams,
    require_permissions,
)
from app.core import permissions as perm
from app.schemas.attendance import (
    AttendanceHistoryItem,
    AttendanceOpen,
    AttendanceOut,
    AttendanceSummary,
    MarkBatch,
    StudentAttendanceOut,
    StudentAttendanceSummary,
    sheet_of,
    summary_of,
)
from app.schemas.common import Page
from app.services import attendance as attendance_service

router = APIRouter(prefix="/attendance", tags=["attendance"])

_ReadDep = Depends(require_permissions(perm.ATTENDANCE_READ))
# Opening a register, marking it, and throwing one away are three different
# acts: a teacher does the first two daily, and the third destroys a day's
# marks for a whole class.
_CreateDep = Depends(require_permissions(perm.ATTENDANCE_CREATE))
_MarkDep = Depends(require_permissions(perm.ATTENDANCE_UPDATE))
_DeleteDep = Depends(require_permissions(perm.ATTENDANCE_DELETE))


@router.post(
    "",
    response_model=AttendanceOut,
    status_code=status.HTTP_201_CREATED,
)
async def open_attendance(
    body: AttendanceOpen,
    db: DBSession,
    auth: Annotated[AuthContext, _CreateDep],
) -> AttendanceOut:
    """Open the register for a class on a date. Every student starts unmarked.

    409 if one already exists — the response carries its id, so a client that
    lost the race can go straight to editing it.
    """
    sheet = await attendance_service.open_sheet(
        db, class_id=body.class_id, on=body.date, marked_by_id=auth.user.id
    )
    await db.commit()
    roster = await attendance_service.roster(db, sheet.class_id, sheet.date)
    return sheet_of(sheet, roster)


@router.get("", response_model=Page[AttendanceSummary], dependencies=[_ReadDep])
async def list_attendance(
    pagination: Pagination,
    db: DBSession,
    class_id: uuid.UUID | None = None,
    program_id: uuid.UUID | None = None,
    date_from: Annotated[date_type | None, Query(description="Inclusive")] = None,
    date_to: Annotated[date_type | None, Query(description="Inclusive")] = None,
) -> Page[AttendanceSummary]:
    """Registers newest-first, each with its present/absent/leave tallies."""
    attendance_service.assert_date_range(date_from, date_to)
    sheets, total = await attendance_service.list_sheets(
        db,
        limit=pagination.limit,
        offset=pagination.offset,
        class_id=class_id,
        program_id=program_id,
        date_from=date_from,
        date_to=date_to,
    )
    items = [
        summary_of(sheet, await attendance_service.roster(db, sheet.class_id, sheet.date))
        for sheet in sheets
    ]
    return Page(items=items, total=total, limit=pagination.limit, offset=pagination.offset)


@router.get("/{attendance_id}", response_model=AttendanceOut, dependencies=[_ReadDep])
async def get_attendance(attendance_id: uuid.UUID, db: DBSession) -> AttendanceOut:
    """The full register: every student on the roster, in roll-number order."""
    sheet = await attendance_service.get_sheet(db, attendance_id)
    roster = await attendance_service.roster(db, sheet.class_id, sheet.date)
    return sheet_of(sheet, roster)


@router.patch("/{attendance_id}", response_model=AttendanceOut, dependencies=[_MarkDep])
async def mark_attendance(
    attendance_id: uuid.UUID,
    body: MarkBatch,
    db: DBSession,
    auth: Annotated[AuthContext, _MarkDep],
) -> AttendanceOut:
    """Mark only the students named. Everyone else is left as they are."""
    sheet = await attendance_service.set_records(
        db,
        attendance_id,
        [m.model_dump() for m in body.marks],
        marked_by_id=auth.user.id,
        replace=False,
    )
    await db.commit()
    roster = await attendance_service.roster(db, sheet.class_id, sheet.date)
    return sheet_of(sheet, roster)


@router.put("/{attendance_id}", response_model=AttendanceOut, dependencies=[_MarkDep])
async def replace_attendance(
    attendance_id: uuid.UUID,
    body: MarkBatch,
    db: DBSession,
    auth: Annotated[AuthContext, _MarkDep],
) -> AttendanceOut:
    """Save the whole register.

    Students omitted from the list go back to unmarked — that is what replacing
    a register means. Use PATCH to touch only some of them.
    """
    sheet = await attendance_service.set_records(
        db,
        attendance_id,
        [m.model_dump() for m in body.marks],
        marked_by_id=auth.user.id,
        replace=True,
    )
    await db.commit()
    roster = await attendance_service.roster(db, sheet.class_id, sheet.date)
    return sheet_of(sheet, roster)


@router.delete(
    "/{attendance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_DeleteDep],
)
async def delete_attendance(attendance_id: uuid.UUID, db: DBSession) -> None:
    """The class did not meet after all. The marks go with the sheet."""
    await attendance_service.delete_sheet(db, attendance_id)
    await db.commit()


async def student_report(
    db: AsyncSession,
    student_id: uuid.UUID,
    *,
    pagination: PaginationParams,
    date_from: date_type | None,
    date_to: date_type | None,
) -> StudentAttendanceOut:
    """One student's totals and history.

    Lives here rather than in the students router because two callers ask the
    same question about different subjects: staff about any student, and the
    portal about the student holding the token.
    """
    attendance_service.assert_date_range(date_from, date_to)
    summary = await attendance_service.student_summary(
        db, student_id, date_from=date_from, date_to=date_to
    )
    rows, total = await attendance_service.student_history(
        db,
        student_id,
        limit=pagination.limit,
        offset=pagination.offset,
        date_from=date_from,
        date_to=date_to,
    )
    return StudentAttendanceOut(
        summary=StudentAttendanceSummary(**summary),
        history=[
            AttendanceHistoryItem(
                date=sheet.date,
                class_id=sheet.class_id,
                status=record.status,
                note=record.note,
            )
            for record, sheet in rows
        ],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )
