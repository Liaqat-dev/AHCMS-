"""Subject — a taught subject, shared across classes.

Many-to-many with ``Class`` through ``class_subjects``: a class runs several
subjects, and one subject ("Mathematics I") is taught to several classes rather
than being duplicated per class.

``teacher_id`` names the faculty member who teaches it. Nullable, because a
subject is usually created before the timetable is settled.

``student_limit`` (default 30) caps how many students may take the subject.
``student_count`` is a cache of the ``subject_enrollments`` rows, maintained
solely by ``app.services.capacity``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.class_ import Class
from app.db.models.faculty import Faculty
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

#: Seats a new subject offers unless the caller says otherwise.
DEFAULT_STUDENT_LIMIT = 30

#: A subject code is short and quoted elsewhere ("MATH101"), so it is capped
#: rather than free text.
SUBJECT_CODE_MAX_LENGTH = 16

# CASCADE on both sides: this table carries no facts of its own, so a deleted
# class or subject should take its links with it rather than block.
class_subjects = Table(
    "class_subjects",
    Base.metadata,
    Column("class_id", ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True),
    Column("subject_id", ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True),
)


class Subject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (
        # The database's own backstop for what the capacity service checks.
        CheckConstraint("student_count >= 0", name="ck_subjects_student_count_positive"),
        CheckConstraint("student_limit > 0", name="ck_subjects_student_limit_positive"),
        CheckConstraint("student_count <= student_limit", name="ck_subjects_count_within_limit"),
    )

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(
        String(SUBJECT_CODE_MAX_LENGTH), unique=True, index=True, nullable=False
    )

    student_limit: Mapped[int] = mapped_column(
        Integer,
        default=DEFAULT_STUDENT_LIMIT,
        server_default=str(DEFAULT_STUDENT_LIMIT),
        nullable=False,
    )
    # A cache of the subject_enrollments rows, not an independent fact. Only
    # app.services.capacity writes it, with a conditional UPDATE that cannot
    # overbook; app.cli.reconcile_counts recomputes it if it ever drifts.
    student_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    # RESTRICT rather than SET NULL: a subject quietly losing its teacher
    # because somebody tidied up a personnel file is the kind of change nobody
    # notices until a timetable is printed. The service refuses with a 409
    # naming the subjects instead.
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("faculty.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    #: Rendered by every subject response, so eager-loaded like `classes`.
    teacher: Mapped[Faculty | None] = relationship(lazy="selectin")

    # Small collection rendered by every response, so eager-load it the way
    # Role.permissions does rather than paying an N+1 per list row.
    classes: Mapped[list[Class]] = relationship(secondary=class_subjects, lazy="selectin")
