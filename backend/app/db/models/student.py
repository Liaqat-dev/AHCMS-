"""Student record, admission details, and portal credentials.

A student is deliberately **not** a ``User``: they hold no roles and no
permissions. They authenticate against this table with ``roll_no`` + password
and reach only their own portal. Staff manage students through
``/api/v1/students`` under the ``students:read``/``students:write`` permissions.

Only name and session are required. In practice a record is opened at
admission and the rest — CNICs, guardian details, SSC results — arrives over
the following weeks, so demanding it up front would only produce placeholder
data. ``missing_fields`` reports what is still outstanding.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.academic_session import AcademicSession
    from app.db.models.enrollment import Enrollment

#: Fields that make an admission record complete, for `missing_fields`.
REQUIRED_FOR_COMPLETION = (
    "b_form_cnic",
    "date_of_birth",
    "father_name",
    "father_cnic",
    "mother_name",
    "cell_no",
    "address",
    "last_school_name",
    "ssc_roll_no",
    "ssc_marks_obtained",
)


class Student(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "students"

    # Allocated by app.services.sessions.allocate_roll_no as "<start_year>-NNN"
    # (e.g. "2022-001"). Also the student's portal login identifier.
    roll_no: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), index=True, nullable=False
    )

    # ----- Identity ---------------------------------------------------------
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # B-Form (under 18) or CNIC, stored as 13 bare digits with the dashes
    # stripped — otherwise "42101-1234567-1" and "4210112345671" are two
    # different rows and the uniqueness guarantee quietly does nothing.
    b_form_cnic: Mapped[str | None] = mapped_column(
        String(13), unique=True, index=True, nullable=True
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ----- Guardians --------------------------------------------------------
    father_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # Not unique: siblings legitimately share a father's CNIC.
    father_cnic: Mapped[str | None] = mapped_column(String(13), index=True, nullable=True)
    mother_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # The number the college actually rings when a student is unwell or absent.
    # One per family rather than one per parent: the office needs a guardian on
    # the phone, not a record of who owns which handset.
    guardian_cell_no: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ----- Contact ----------------------------------------------------------
    cell_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    province: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Domicile, not residence: it is the district on the certificate, which is
    # what quotas and board paperwork are decided on, and it frequently differs
    # from where the family currently lives.
    domicile_district: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ----- Prior education (SSC / Matric) -----------------------------------
    last_school_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ssc_roll_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Stored as obtained/total rather than a percentage, because boards differ
    # on the total and a stored percentage cannot be re-derived or corrected.
    ssc_marks_obtained: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    ssc_marks_total: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    ssc_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # ----- Portal account ---------------------------------------------------
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True, nullable=True)
    # NULL means no password has been issued yet (e.g. a bulk-imported record);
    # login is refused until staff set one via PUT /students/{id}/password.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    session: Mapped[AcademicSession] = relationship(back_populates="students")
    # At most one, enforced by UNIQUE(student_id) on the enrollments side.
    # `raise` because most student queries do not need it; the ones that render
    # it load it explicitly.
    enrollment: Mapped[Enrollment | None] = relationship(back_populates="student", lazy="raise")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def ssc_percentage(self) -> float | None:
        """Derived, never stored — so a corrected total fixes it everywhere."""
        if not self.ssc_marks_obtained or not self.ssc_marks_total:
            return None
        return round(self.ssc_marks_obtained * 100 / self.ssc_marks_total, 2)

    @property
    def missing_fields(self) -> list[str]:
        return [f for f in REQUIRED_FOR_COMPLETION if getattr(self, f) is None]

    @property
    def is_profile_complete(self) -> bool:
        return not self.missing_fields
