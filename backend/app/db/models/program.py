"""Program — a course of study a student is admitted to, e.g. "Engineering".

Two identifiers, both unique: the full ``name`` and a three-letter ``code``
("ENG") short enough to sit in a roll number, a timetable cell, or a report
column. The code is stored upper-case; normalization happens in the schema so
there is exactly one spelling of a program in the database.

``created_by`` is an audit trail, not ownership — it does not grant its holder
any rights over the row, and it goes NULL rather than blocking if that staff
account is ever removed.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.user import User

#: A program code is exactly this many characters ("ENG", "BBA", "CSE").
PROGRAM_CODE_LENGTH = 3


class Program(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "programs"

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(
        String(PROGRAM_CODE_LENGTH), unique=True, index=True, nullable=False
    )

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    created_by: Mapped[User | None] = relationship(lazy="raise")
