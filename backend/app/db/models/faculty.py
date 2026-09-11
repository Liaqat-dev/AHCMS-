"""Faculty — the teaching and support staff on the college's books.

An HR record, deliberately separate from ``User``: a lecturer who never signs
in still has to appear on a timetable and a salary sheet, and a staff account
that exists only to administer the system is not faculty. The two are joined
only if and when somebody decides they should be.

``employee_no`` is to faculty what ``roll_no`` is to a student: the identifier
people actually quote. Unlike a roll number it is entered rather than
allocated, because it usually already exists on paper before the record does.

Only the employee number and a name are required. The rest of a personnel file
arrives over time, exactly as a student's admission file does.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

#: Fields that make a personnel file complete, for `missing_fields`.
REQUIRED_FOR_COMPLETION = (
    "designation",
    "qualification",
    "cnic",
    "cell_no",
    "joined_on",
)


class Faculty(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "faculty"

    employee_no: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    #: "Lecturer", "Assistant Professor", "Lab Assistant" — free text, because
    #: the ladder differs between institutions and a fixed enum would need a
    #: migration the first time one of them is renamed.
    designation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    qualification: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # Stored as 13 bare digits with the dashes stripped, like a student's —
    # otherwise "42101-1234567-1" and "4210112345671" are two different rows
    # and the uniqueness guarantee quietly does nothing.
    cnic: Mapped[str | None] = mapped_column(String(13), unique=True, index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True, nullable=True)
    cell_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: The staff account this person signs in with, if they have one.
    #:
    #: Unique and nullable: plenty of faculty never touch the system, and no
    #: login belongs to two people. This is what makes "only the teacher of
    #: this subject may enter its marks" answerable — the request carries a
    #: ``User``, the subject names a ``Faculty``, and this joins them.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, index=True, nullable=True
    )

    joined_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Kept rather than deleted when someone leaves: a past register, and any
    #: subject they taught, should still be able to name them.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def missing_fields(self) -> list[str]:
        return [name for name in REQUIRED_FOR_COMPLETION if getattr(self, name) is None]
