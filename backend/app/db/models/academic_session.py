"""Academic session: the two-year batch a student is admitted into.

Named ``AcademicSession`` rather than ``Session`` on purpose — the plain name
would collide with SQLAlchemy's ``AsyncSession`` and with ``RefreshSession`` in
``app.db.models.session``, which are unrelated concepts. The API and the
permission codes still call it a *session* (``sessions:read`` /
``sessions:write``).

It carries exactly two things: the batch's start year, and the counter behind
that batch's roll numbers. ``end_year`` and ``label`` are derived, not stored,
so there is only ever one fact to keep correct.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.student import Student

#: Every session runs for exactly two years, e.g. 2022-2024.
SESSION_LENGTH_YEARS = 2


class AcademicSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "academic_sessions"

    # One row per intake year, so the 2022 batch cannot be created twice.
    start_year: Mapped[int] = mapped_column(SmallInteger, unique=True, nullable=False)

    # Next roll number to hand out in this batch. Never decremented: a
    # rolled-back admission leaves a gap, which is deliberate — gaps are
    # cosmetic, whereas a reused number would collide on a student's login id.
    next_roll_seq: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )

    students: Mapped[list[Student]] = relationship(back_populates="session")

    @property
    def end_year(self) -> int:
        return self.start_year + SESSION_LENGTH_YEARS

    @property
    def label(self) -> str:
        return f"{self.start_year}-{self.end_year}"
