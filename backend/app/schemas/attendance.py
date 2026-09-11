"""Attendance schemas.

A sheet reads as the class roster with each student's mark beside it, so the
response is built from the *current* roster rather than from the stored rows
alone: a student nobody has called yet appears with ``status: null``, which is
what "unmarked" means here.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel, Field

from app.db.models.attendance import ATTENDANCE_STATUSES, AttendanceRecord, AttendanceSheet
from app.db.models.student import Student

#: Mirrors the model's CHECK constraint, so an unknown value is a 422 from
#: FastAPI's own validation before the service is reached. Spelled out rather
#: than built from ATTENDANCE_STATUSES because Literal needs literals; the
#: check below keeps the two honest.
AttendanceStatus = Literal["present", "absent", "leave"]

if set(get_args(AttendanceStatus)) != set(ATTENDANCE_STATUSES):  # pragma: no cover
    raise RuntimeError("AttendanceStatus is out of step with the model's status list")


class AttendanceOpen(BaseModel):
    class_id: uuid.UUID
    #: Omit for today at the college (COLLEGE_TIMEZONE), not on the UTC server.
    #: A future date is refused.
    date: date_type | None = None


class MarkIn(BaseModel):
    student_id: uuid.UUID
    #: ``null`` clears the mark — back to unmarked, which is not the same as
    #: absent.
    status: AttendanceStatus | None = None
    note: str | None = Field(default=None, max_length=255)


class MarkBatch(BaseModel):
    marks: list[MarkIn]


class StudentRef(BaseModel):
    id: uuid.UUID
    roll_no: str
    first_name: str
    last_name: str

    model_config = {"from_attributes": True}


class ClassRef(BaseModel):
    id: uuid.UUID
    name: str
    program_id: uuid.UUID
    program_code: str

    model_config = {"from_attributes": True}


class MarkOut(BaseModel):
    student: StudentRef
    #: Null when nobody has marked this student yet.
    status: AttendanceStatus | None = None
    note: str | None = None
    marked_by_id: uuid.UUID | None = None
    marked_at: datetime | None = None
    #: True when the mark belongs to a student who is no longer on the roster —
    #: they left the class after being marked. The record is kept; the read is
    #: honest about it rather than hiding the row.
    off_roster: bool = False


class AttendanceCounts(BaseModel):
    present: int = 0
    absent: int = 0
    leave: int = 0
    unmarked: int = 0
    total: int = 0


class AttendanceSummary(BaseModel):
    """A register as it appears in a list: who, when, and the tallies."""

    id: uuid.UUID
    class_: ClassRef = Field(serialization_alias="class", validation_alias="class")
    date: date_type
    marked_by_id: uuid.UUID | None
    counts: AttendanceCounts
    created_at: datetime

    model_config = {"populate_by_name": True}


class AttendanceOut(AttendanceSummary):
    """The full register: every student on the roster, in roll-number order."""

    marks: list[MarkOut]


def _class_ref(sheet: AttendanceSheet) -> ClassRef:
    return ClassRef(
        id=sheet.class_.id,
        name=sheet.class_.name,
        program_id=sheet.class_.program_id,
        program_code=sheet.class_.program.code,
    )


def build_marks(sheet: AttendanceSheet, roster: list[Student]) -> list[MarkOut]:
    """The roster joined to the stored marks.

    Driven by the roster, not by the records: everyone who should be on the
    sheet appears, marked or not. Records for students who have since left the
    class are appended and flagged rather than dropped.
    """
    records: dict[uuid.UUID, AttendanceRecord] = {r.student_id: r for r in sheet.records}

    marks = []
    for student in roster:
        record = records.pop(student.id, None)
        marks.append(
            MarkOut(
                student=StudentRef.model_validate(student),
                status=record.status if record else None,
                note=record.note if record else None,
                marked_by_id=record.marked_by_id if record else None,
                marked_at=record.marked_at if record else None,
            )
        )

    for record in records.values():
        marks.append(
            MarkOut(
                student=StudentRef.model_validate(record.student),
                status=record.status,
                note=record.note,
                marked_by_id=record.marked_by_id,
                marked_at=record.marked_at,
                off_roster=True,
            )
        )
    return marks


def _counts(marks: list[MarkOut]) -> AttendanceCounts:
    counts = AttendanceCounts(total=len(marks))
    for mark in marks:
        if mark.status is None:
            counts.unmarked += 1
        else:
            setattr(counts, mark.status, getattr(counts, mark.status) + 1)
    return counts


def summary_of(sheet: AttendanceSheet, roster: list[Student]) -> AttendanceSummary:
    return AttendanceSummary(
        id=sheet.id,
        date=sheet.date,
        marked_by_id=sheet.marked_by_id,
        counts=_counts(build_marks(sheet, roster)),
        created_at=sheet.created_at,
        **{"class": _class_ref(sheet)},
    )


def sheet_of(sheet: AttendanceSheet, roster: list[Student]) -> AttendanceOut:
    marks = build_marks(sheet, roster)
    return AttendanceOut(
        id=sheet.id,
        date=sheet.date,
        marked_by_id=sheet.marked_by_id,
        counts=_counts(marks),
        marks=marks,
        created_at=sheet.created_at,
        **{"class": _class_ref(sheet)},
    )


class StudentAttendanceSummary(BaseModel):
    """One student's totals.

    ``percentage`` is present out of (present + absent) — approved ``leave`` is
    excluded from the denominator, so taking leave neither counts as attending
    nor drags the number down. Null when there is nothing to divide by, which
    is not the same as zero.
    """

    student_id: uuid.UUID
    eligible_days: int
    marked_days: int
    unmarked_days: int
    present: int
    absent: int
    leave: int
    percentage: float | None


class AttendanceHistoryItem(BaseModel):
    date: date_type
    class_id: uuid.UUID
    status: AttendanceStatus
    note: str | None = None


class StudentAttendanceOut(BaseModel):
    summary: StudentAttendanceSummary
    history: list[AttendanceHistoryItem]
    total: int
    limit: int
    offset: int
