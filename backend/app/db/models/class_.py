"""Class — a teaching group inside a program, e.g. "ENG-1A".

One program has many classes; a class belongs to exactly one program and
cannot outlive it. The name is unique *within* its program, not globally, so
two programs can both run a "Morning" or a "1st Year" class without either
having to invent a prefix.

A class has no seat limit of its own — capacity is a per-subject concern, and
a class is just the group a student belongs to.

Module named ``class_`` (and locals ``class_``) because ``class`` is a Python
keyword; the ORM class, the table, and the API all still call it a class.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.program import Program


class Class(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "classes"
    __table_args__ = (UniqueConstraint("program_id", "name", name="uq_classes_program_name"),)

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    # RESTRICT, not CASCADE: deleting a program must not silently take its
    # classes (and whatever comes to hang off them) with it. The service turns
    # the violation into a 409 before the database has to.
    program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("programs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    # ClassOut always renders the program, so it is loaded explicitly in the
    # service; `raise` makes an accidental N+1 loud instead of silent.
    program: Mapped[Program] = relationship(lazy="raise")
