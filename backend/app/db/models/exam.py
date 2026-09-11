"""Exams, the subjects they cover, and the marks recorded against them.

An exam belongs to a class and happens on a date. It covers either **one
subject** or **every subject the class runs** — and either way the subjects it
covers are written down at creation time in ``exam_subjects`` rather than
derived later. A class's subject list changes; an exam that happened in March
covered what it covered in March, and a report printed in June has to say so.

Marks hang off the *exam subject*, not the exam: each subject has its own total,
its own roster (the students who chose it), and its own teacher. That last one
matters, because only that teacher may enter its marks.

Unlike an attendance register, an exam may be dated in the **future** — the
point of scheduling one is to announce it before it happens.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import college_now
from app.db.base import Base
from app.db.models.class_ import Class
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.subject import Subject

if TYPE_CHECKING:
    from app.db.models.student import Student

#: What an exam covers. Recorded because "one subject" and "all of them" are
#: different intentions even when a class happens to run a single subject.
SCOPE_SUBJECT = "subject"
SCOPE_CLASS = "class"
EXAM_SCOPES = (SCOPE_SUBJECT, SCOPE_CLASS)

DEFAULT_TOTAL_MARKS = 100


class Exam(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exams"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('{}')".format("', '".join(EXAM_SCOPES)), name="ck_exams_scope"
        ),
    )

    title: Mapped[str] = mapped_column(String(150), nullable=False)
    #: RESTRICT: an exam is a record of something that happened to a class.
    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    #: The day it is sat. May be in the future — exams are announced in advance.
    date: Mapped[date_type] = mapped_column(Date, index=True, nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    class_: Mapped[Class] = relationship(lazy="raise")
    subjects: Mapped[list[ExamSubject]] = relationship(
        back_populates="exam", cascade="all, delete-orphan", lazy="raise"
    )


class ExamSubject(UUIDPrimaryKeyMixin, Base):
    """One subject within an exam: its paper, its total, its marks."""

    __tablename__ = "exam_subjects"
    __table_args__ = (
        UniqueConstraint("exam_id", "subject_id", name="uq_exam_subjects_pair"),
        CheckConstraint("total_marks > 0", name="ck_exam_subjects_total_positive"),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    #: RESTRICT: deleting a subject somebody has been examined in would take the
    #: marks with it.
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    total_marks: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_TOTAL_MARKS, server_default=str(DEFAULT_TOTAL_MARKS),
        nullable=False,
    )

    exam: Mapped[Exam] = relationship(back_populates="subjects", lazy="raise")
    subject: Mapped[Subject] = relationship(lazy="raise")
    marks: Mapped[list[ExamMark]] = relationship(
        back_populates="exam_subject", cascade="all, delete-orphan", lazy="raise"
    )


class ExamMark(UUIDPrimaryKeyMixin, Base):
    """One student's result in one subject of one exam.

    A row exists only once somebody records something. No row means the mark
    has not been entered yet, which is different from a zero.
    """

    __tablename__ = "exam_marks"
    __table_args__ = (
        UniqueConstraint("exam_subject_id", "student_id", name="uq_exam_marks_pair"),
        CheckConstraint("obtained IS NULL OR obtained >= 0", name="ck_exam_marks_positive"),
        # Absent and a score are mutually exclusive: one of them is the answer.
        CheckConstraint(
            "NOT (is_absent AND obtained IS NOT NULL)", name="ck_exam_marks_absent_or_score"
        ),
    )

    exam_subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )

    obtained: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_absent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    marked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    marked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=college_now, server_default=func.now(), nullable=False
    )

    exam_subject: Mapped[ExamSubject] = relationship(back_populates="marks", lazy="raise")
    student: Mapped[Student] = relationship(lazy="raise")
