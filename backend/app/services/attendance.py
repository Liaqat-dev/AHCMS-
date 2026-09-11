"""Attendance registers: one sheet per class per day, marked by any staff.

Two rules the database cannot state live here:

* a sheet's roster is the students enrolled in that class **on or before** the
  sheet's date — a student's attendance starts on their enrolment day, and
  nobody is marked for a class they had not yet joined;
* a sheet cannot be dated in the future, where "today" means today at the
  college (``app.core.clock``), not on the UTC server.

Records are created only when somebody marks: a student with no record is
*unmarked*, which is different from present and from absent.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import college_now, college_today, end_of_day, to_college_date
from app.db.models import AttendanceRecord, AttendanceSheet, Class, Enrollment, Student
from app.db.models.attendance import ATTENDANCE_STATUSES, STATUS_LEAVE, STATUS_PRESENT
from app.exceptions.errors import BadRequest, Conflict, NotFound, Unprocessable
from app.services import classes as classes_service

#: The sheet response renders the class, its program, and every mark with the
#: student behind it. All three relationships are lazy="raise".
_FULL = (
    selectinload(AttendanceSheet.class_).selectinload(Class.program),
    selectinload(AttendanceSheet.records).selectinload(AttendanceRecord.student),
)


# --------------------------------------------------------------------- reads
async def get_sheet(db: AsyncSession, sheet_id: uuid.UUID) -> AttendanceSheet:
    sheet = await db.scalar(
        select(AttendanceSheet).where(AttendanceSheet.id == sheet_id).options(*_FULL)
    )
    if sheet is None:
        raise NotFound("Attendance sheet not found")
    return sheet


async def get_sheet_for(db: AsyncSession, class_id: uuid.UUID, on: date_type) -> AttendanceSheet:
    sheet = await db.scalar(
        select(AttendanceSheet)
        .where(AttendanceSheet.class_id == class_id, AttendanceSheet.date == on)
        .options(*_FULL)
    )
    if sheet is None:
        raise NotFound(f"This class has no attendance for {on.isoformat()}")
    return sheet


async def list_sheets(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    class_id: uuid.UUID | None = None,
    program_id: uuid.UUID | None = None,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
) -> tuple[list[AttendanceSheet], int]:
    """Registers newest-first. Counts are derived per sheet by the caller."""
    filters = []
    if class_id is not None:
        filters.append(AttendanceSheet.class_id == class_id)
    if program_id is not None:
        filters.append(
            AttendanceSheet.class_id.in_(select(Class.id).where(Class.program_id == program_id))
        )
    if date_from is not None:
        filters.append(AttendanceSheet.date >= date_from)
    if date_to is not None:
        filters.append(AttendanceSheet.date <= date_to)

    total_query = select(func.count()).select_from(AttendanceSheet)
    list_query = select(AttendanceSheet).options(*_FULL)
    for condition in filters:
        total_query = total_query.where(condition)
        list_query = list_query.where(condition)

    total = await db.scalar(total_query) or 0
    sheets = (
        await db.scalars(
            list_query.order_by(AttendanceSheet.date.desc()).limit(limit).offset(offset)
        )
    ).all()
    return list(sheets), total


# ------------------------------------------------------------------- roster
async def roster(db: AsyncSession, class_id: uuid.UUID, on: date_type) -> list[Student]:
    """Who belongs on a sheet for this class on this date, by roll number.

    Enrolled in the class, and enrolled **on or before** the date: a student who
    joined on the 10th is not on the 3rd's register at all, so their percentage
    starts the day they arrived rather than opening with a week of absences.
    """
    return list(
        (
            await db.scalars(
                select(Student)
                .join(Enrollment, Enrollment.student_id == Student.id)
                .where(
                    Enrollment.class_id == class_id,
                    # "on or before this day" as an instant comparison — see
                    # clock.end_of_day for why this is not a cast to date.
                    Enrollment.enrolled_at < end_of_day(on),
                )
                .order_by(Student.roll_no)
            )
        ).all()
    )


# -------------------------------------------------------------------- writes
def _assert_not_future(on: date_type) -> None:
    today = college_today()
    if on > today:
        raise Unprocessable(
            "Attendance cannot be taken for a future date",
            details={"date": on.isoformat(), "today": today.isoformat()},
        )


async def open_sheet(
    db: AsyncSession,
    *,
    class_id: uuid.UUID,
    on: date_type | None,
    marked_by_id: uuid.UUID | None,
) -> AttendanceSheet:
    """Open the register for a class on a date. Every student starts unmarked.

    No rows are seeded: an unmarked student is one nobody has called yet, which
    a sheet full of pre-set "present" values could not express.
    """
    on = on or college_today()
    _assert_not_future(on)

    class_ = await classes_service.get_class(db, class_id)

    existing = await db.scalar(
        select(AttendanceSheet.id).where(
            AttendanceSheet.class_id == class_.id, AttendanceSheet.date == on
        )
    )
    if existing:
        # Carry the id so a client that lost the race can jump straight to
        # editing the sheet instead of hitting a dead end.
        raise Conflict(
            f"{class_.name} already has attendance for {on.isoformat()}",
            details={"attendance_id": str(existing), "date": on.isoformat()},
        )

    if not await roster(db, class_.id, on):
        raise Conflict(
            "No students were enrolled in this class on that date",
            details={"class_id": str(class_.id), "date": on.isoformat()},
        )

    sheet = AttendanceSheet(class_id=class_.id, date=on, marked_by_id=marked_by_id)
    sheet.class_ = class_
    sheet.records = []
    db.add(sheet)
    await db.flush()
    return sheet


async def _validate_marks(
    db: AsyncSession, sheet: AttendanceSheet, marks: list[dict]
) -> dict[uuid.UUID, dict]:
    """Check every mark against the roster and the status list.

    Returns them keyed by student, with duplicates collapsed to the last one —
    a client sending the same student twice means the second answer.
    """
    by_student: dict[uuid.UUID, dict] = {}
    for mark in marks:
        by_student[mark["student_id"]] = mark

    bad_status = sorted(
        {
            m["status"]
            for m in by_student.values()
            if m.get("status") is not None and m["status"] not in ATTENDANCE_STATUSES
        }
    )
    if bad_status:
        raise Unprocessable(
            "Unknown attendance status",
            details={"statuses": bad_status, "allowed": list(ATTENDANCE_STATUSES)},
        )

    eligible = {s.id for s in await roster(db, sheet.class_id, sheet.date)}
    outside = sorted(str(sid) for sid in by_student.keys() - eligible)
    if outside:
        # 422, not 409: the student was not in this class on this date, so the
        # identical request will never succeed.
        raise Unprocessable(
            "These students were not enrolled in this class on that date",
            details={"student_ids": outside, "date": sheet.date.isoformat()},
        )
    return by_student


async def set_records(
    db: AsyncSession,
    sheet_id: uuid.UUID,
    marks: list[dict],
    *,
    marked_by_id: uuid.UUID | None,
    replace: bool,
) -> AttendanceSheet:
    """Apply marks to a sheet.

    ``replace`` is the difference between the two write verbs. A PATCH touches
    only the students named. A PUT is the whole sheet as saved, so students it
    omits go back to unmarked — that is what replacing a register means.

    A mark with ``status: null`` clears that student's mark either way.
    """
    sheet = await get_sheet(db, sheet_id)
    by_student = await _validate_marks(db, sheet, marks)

    existing = {r.student_id: r for r in sheet.records}
    now = college_now()

    if replace:
        for student_id in existing.keys() - by_student.keys():
            sheet.records.remove(existing[student_id])

    for student_id, mark in by_student.items():
        record = existing.get(student_id)
        if mark.get("status") is None:
            # Explicitly unmarking someone.
            if record is not None:
                sheet.records.remove(record)
            continue

        if record is None:
            record = AttendanceRecord(sheet_id=sheet.id, student_id=student_id)
            sheet.records.append(record)
        record.status = mark["status"]
        if "note" in mark:
            record.note = mark["note"]
        record.marked_by_id = marked_by_id
        record.marked_at = now

    await db.flush()
    # The collection was edited in place; reload it with students attached so
    # the caller can render the sheet.
    return await get_sheet(db, sheet.id)


async def delete_sheet(db: AsyncSession, sheet_id: uuid.UUID) -> None:
    """The class did not meet after all. Marks cascade."""
    sheet = await get_sheet(db, sheet_id)
    await db.delete(sheet)
    await db.flush()


async def count_for_class(db: AsyncSession, class_id: uuid.UUID) -> int:
    """Registers behind a class. Guards the class's deletion."""
    return (
        await db.scalar(
            select(func.count())
            .select_from(AttendanceSheet)
            .where(AttendanceSheet.class_id == class_id)
        )
        or 0
    )


# ----------------------------------------------------------------- reporting
async def student_summary(
    db: AsyncSession,
    student_id: uuid.UUID,
    *,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
) -> dict:
    """One student's attendance, counted from the day they enrolled.

    ``eligible`` is how many registers they should appear on — sheets for their
    class dated on or after their enrolment — so a student who joined in March
    is not measured against February.

    The percentage excludes ``leave`` from the denominator: approved leave
    neither counts as attending nor drags the number down. Every raw count is
    returned alongside it, so a different rule can be applied by the reader
    without re-querying.
    """
    student = await db.get(Student, student_id)
    if student is None:
        raise NotFound("Student not found")

    marks = select(AttendanceRecord.status, AttendanceSheet.date, AttendanceSheet.class_id).join(
        AttendanceSheet, AttendanceSheet.id == AttendanceRecord.sheet_id
    )
    marks = marks.where(AttendanceRecord.student_id == student_id)
    if date_from is not None:
        marks = marks.where(AttendanceSheet.date >= date_from)
    if date_to is not None:
        marks = marks.where(AttendanceSheet.date <= date_to)

    counts = dict.fromkeys(ATTENDANCE_STATUSES, 0)
    for status, _date, _class_id in (await db.execute(marks)).all():
        counts[status] = counts.get(status, 0) + 1

    # Registers the student should have been on: their class, from their
    # enrolment day onward.
    enrollment = await db.scalar(select(Enrollment).where(Enrollment.student_id == student_id))
    eligible = 0
    if enrollment is not None:
        sheets = (
            select(func.count())
            .select_from(AttendanceSheet)
            .where(
                AttendanceSheet.class_id == enrollment.class_id,
                # A loaded row, so this is a Python datetime — read it as the
                # college's day, not the server's.
                AttendanceSheet.date >= to_college_date(enrollment.enrolled_at),
            )
        )
        if date_from is not None:
            sheets = sheets.where(AttendanceSheet.date >= date_from)
        if date_to is not None:
            sheets = sheets.where(AttendanceSheet.date <= date_to)
        eligible = await db.scalar(sheets) or 0

    marked = sum(counts.values())
    counted = marked - counts[STATUS_LEAVE]
    percentage = round(counts[STATUS_PRESENT] / counted * 100, 1) if counted else None

    return {
        "student_id": student_id,
        "eligible_days": eligible,
        "marked_days": marked,
        "unmarked_days": max(eligible - marked, 0),
        "present": counts[STATUS_PRESENT],
        "absent": counts["absent"],
        "leave": counts[STATUS_LEAVE],
        # None rather than 0.0 when there is nothing to divide by: "no data" and
        # "attended none of it" are very different answers.
        "percentage": percentage,
    }


async def student_history(
    db: AsyncSession,
    student_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
) -> tuple[list[tuple[AttendanceRecord, AttendanceSheet]], int]:
    """The student's marks, newest first, with the sheet each belongs to."""
    base = (
        select(AttendanceRecord, AttendanceSheet)
        .join(AttendanceSheet, AttendanceSheet.id == AttendanceRecord.sheet_id)
        .where(AttendanceRecord.student_id == student_id)
    )
    conditions = []
    if date_from is not None:
        conditions.append(AttendanceSheet.date >= date_from)
    if date_to is not None:
        conditions.append(AttendanceSheet.date <= date_to)
    for condition in conditions:
        base = base.where(condition)

    total_query = (
        select(func.count())
        .select_from(AttendanceRecord)
        .join(AttendanceSheet, AttendanceSheet.id == AttendanceRecord.sheet_id)
        .where(AttendanceRecord.student_id == student_id)
    )
    for condition in conditions:
        total_query = total_query.where(condition)

    total = await db.scalar(total_query) or 0
    rows = (
        await db.execute(base.order_by(AttendanceSheet.date.desc()).limit(limit).offset(offset))
    ).all()
    return [(row[0], row[1]) for row in rows], total


def assert_date_range(date_from: date_type | None, date_to: date_type | None) -> None:
    """Reject a reversed range rather than silently returning nothing."""
    if date_from and date_to and date_from > date_to:
        raise BadRequest(
            "date_from is after date_to",
            details={"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
        )
