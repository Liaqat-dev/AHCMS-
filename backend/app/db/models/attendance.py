"""Attendance: one register per class per calendar day.

``UNIQUE(class_id, date)`` on the sheet is the whole "one attendance per class
per day" rule. A day with **no** sheet is a day the class did not meet — a
holiday, a Sunday — so nothing needs a calendar of non-teaching days, and every
percentage is computed over the sheets that exist.

Records are keyed to ``student_id``, **not** to the enrollment — the opposite
of the subject picks in ``app.db.models.enrollment``. A subject choice only
means anything inside the enrollment that owns it, so it dies with it. An
attendance mark is a fact about a day that already happened: a student who
moves class in March must keep their February register.

A student is only on a sheet from their enrolment day onward; nobody is marked
absent for a class they had not yet joined. That rule lives in
``app.services.attendance``, which builds each sheet's roster from the
enrollments dated on or before the sheet.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import college_now
from app.db.base import Base
from app.db.models.class_ import Class
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.student import Student

#: What a mark can say. Stored as a short string with a CHECK rather than a
#: Postgres ENUM: adding a value to a native enum needs a migration and a lock,
#: while this needs a change here and one to the constraint.
STATUS_PRESENT = "present"
STATUS_ABSENT = "absent"
#: Approved absence. Excluded from the attendance percentage's denominator, so
#: taking leave neither counts as attending nor drags the number down.
STATUS_LEAVE = "leave"

ATTENDANCE_STATUSES = (STATUS_PRESENT, STATUS_ABSENT, STATUS_LEAVE)

_STATUS_CHECK = "status IN ('{}')".format("', '".join(ATTENDANCE_STATUSES))


class AttendanceSheet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_sheets"
    __table_args__ = (UniqueConstraint("class_id", "date", name="uq_attendance_sheets_class_date"),)

    # RESTRICT: deleting a class with a term of registers behind it is a 409
    # from the service, not one click.
    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    #: A calendar day at the college (see app.core.clock), not a timestamp.
    date: Mapped[date_type] = mapped_column(Date, index=True, nullable=False)

    #: Who opened the register. Individual marks carry their own author.
    marked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    class_: Mapped[Class] = relationship(lazy="raise")
    records: Mapped[list[AttendanceRecord]] = relationship(
        back_populates="sheet", cascade="all, delete-orphan", lazy="raise"
    )


class AttendanceRecord(UUIDPrimaryKeyMixin, Base):
    """One student's mark on one sheet.

    A student with no record on a sheet is **unmarked** — not present, not
    absent, simply not yet called. Rows exist only once somebody marks them.
    """

    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("sheet_id", "student_id", name="uq_attendance_records_pair"),
        CheckConstraint(_STATUS_CHECK, name="ck_attendance_records_status"),
    )

    sheet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendance_sheets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # CASCADE: if the person is deleted from the system their marks go too.
    # Unenrolling them does not — that leaves the record where it is.
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )

    status: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Per record, not just per sheet: the register is opened once, but a single
    # mark gets corrected days later by somebody else, and a disputed absence
    # should say who stands behind it.
    marked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    marked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=college_now,
        server_default=func.now(),
        nullable=False,
    )

    sheet: Mapped[AttendanceSheet] = relationship(back_populates="records", lazy="raise")
    student: Mapped[Student] = relationship(lazy="raise")
