"""Enrollment — the one class a student belongs to, and the subjects they take.

``UNIQUE(student_id)`` is the whole "a student enrolls in exactly one class"
rule, held by the database rather than by convention. A student who changes
class updates this row; a student who leaves has it deleted. That deliberately
keeps no history — a second class for the same student is simply impossible.

The subject picks hang off the **enrollment**, not off the student. Two rules
then enforce themselves: a pick cannot exist without a class enrollment, and
moving or deleting the enrollment takes the picks with it. Keyed to the student
instead, both would be service code somebody has to remember to run.

What the schema still cannot express is that a picked subject must be one of
the enrolled class's subjects — that is a three-table join, checked in
``app.services.enrollments`` on every write that can break it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import college_now
from app.db.base import Base
from app.db.models.class_ import Class
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.subject import Subject

if TYPE_CHECKING:
    from app.db.models.student import Student


class Enrollment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enrollments"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # RESTRICT: deleting a class with students in it is a 409 from the service,
    # not a silent unenrollment.
    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    #: When they joined *this* class — reset on a move, unlike created_at.
    #:
    #: Set by the application (see mixins for why): this is the column a
    #: register's roster is built from, so a database clock running ahead of
    #: the app would hide a student from the day they enrolled.
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=college_now,
        server_default=func.now(),
        nullable=False,
    )

    student: Mapped[Student] = relationship(back_populates="enrollment", lazy="raise")
    class_: Mapped[Class] = relationship(lazy="raise")

    # delete-orphan so replacing the collection deletes the rows it drops; the
    # capacity service releases their seats first.
    subject_links: Mapped[list[SubjectEnrollment]] = relationship(
        back_populates="enrollment", cascade="all, delete-orphan", lazy="raise"
    )

    @property
    def subjects(self) -> list[Subject]:
        return [link.subject for link in self.subject_links]


class SubjectEnrollment(UUIDPrimaryKeyMixin, Base):
    """One optional subject a student has taken up within their class."""

    __tablename__ = "subject_enrollments"
    __table_args__ = (
        UniqueConstraint("enrollment_id", "subject_id", name="uq_subject_enrollments_pair"),
    )

    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # RESTRICT, mirroring classes: deleting a subject students have taken up is
    # a 409, so nobody loses a choice as a side effect of tidying up.
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=college_now,
        server_default=func.now(),
        nullable=False,
    )

    enrollment: Mapped[Enrollment] = relationship(back_populates="subject_links", lazy="raise")
    subject: Mapped[Subject] = relationship(lazy="raise")
