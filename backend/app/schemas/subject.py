"""Subject schemas.

``student_count`` is read-only: it is a cache of the ``subject_enrollments``
rows and only ``app.services.capacity`` writes it. Lowering ``student_limit``
below the students already enrolled is refused by the service.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models.subject import (
    DEFAULT_STUDENT_LIMIT,
    SUBJECT_CODE_MAX_LENGTH,
    Subject,
)

#: Shared constraints, spelled once. Codes are letters, digits and dashes: they
#: are quoted in timetables and reports, where spaces would be ambiguous.
_NAME_RULES: dict = {"min_length": 1, "max_length": 150, "examples": ["Mathematics I"]}
_CODE_RULES: dict = {
    "min_length": 2,
    "max_length": SUBJECT_CODE_MAX_LENGTH,
    "pattern": r"^[A-Za-z0-9-]+$",
    "examples": ["MATH101"],
}
_LIMIT_RULES: dict = {"ge": 1, "le": 10_000, "examples": [DEFAULT_STUDENT_LIMIT]}


class _SubjectBase(BaseModel):
    @field_validator("name", "code", check_fields=False)
    @classmethod
    def _not_null(cls, value: str | None) -> str:
        # On the update model these are optional, so an explicit `null` can
        # arrive here. Neither column is nullable, so that is a client mistake
        # rather than "leave it alone".
        if value is None:
            raise ValueError("must not be null; omit the field to leave it unchanged")
        return value

    @field_validator("code", check_fields=False)
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @field_validator("name", check_fields=False)
    @classmethod
    def _trim(cls, value: str) -> str:
        # min_length runs before this, so a name of pure whitespace gets this
        # far; reject it rather than storing "".
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("must not be blank")
        return trimmed


class SubjectCreate(_SubjectBase):
    #: The faculty member who teaches it. Optional: a subject usually exists
    #: before the timetable is settled.
    name: str = Field(**_NAME_RULES)
    code: str = Field(**_CODE_RULES)
    # A new subject offers DEFAULT_STUDENT_LIMIT seats and holds nobody: the
    # count is not accepted here, since enrollment is what moves it.
    student_limit: int = Field(default=DEFAULT_STUDENT_LIMIT, **_LIMIT_RULES)
    teacher_id: uuid.UUID | None = None
    #: Classes this subject is taught to. Optional — a subject can exist before
    #: it is timetabled anywhere.
    class_ids: list[uuid.UUID] = Field(default_factory=list)


class SubjectUpdate(_SubjectBase):
    name: str | None = Field(default=None, **_NAME_RULES)
    code: str | None = Field(default=None, **_CODE_RULES)
    # student_count is deliberately absent: it is a cache of the enrollment
    # rows, maintained by app.services.capacity. Accepting it here would let one
    # request desynchronise the number from the students behind it.
    student_limit: int | None = Field(default=None, **_LIMIT_RULES)
    #: `null` clears the assignment, which is different from omitting it.
    teacher_id: uuid.UUID | None = None


class SubjectClassAssignment(BaseModel):
    """The full set of classes a subject runs in — this replaces the list."""

    class_ids: list[uuid.UUID]


class ClassRef(BaseModel):
    """A class as it appears inside a subject: enough to name it, no more."""

    id: uuid.UUID
    name: str
    program_id: uuid.UUID

    model_config = {"from_attributes": True}


class SubjectOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    teacher_id: uuid.UUID | None = None
    #: Denormalized for display, so a list need not resolve faculty ids itself.
    teacher_name: str | None = None
    teacher_designation: str | None = None
    student_limit: int
    student_count: int
    #: Seats left, derived rather than stored so it cannot drift.
    seats_available: int
    classes: list[ClassRef]
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_subject(cls, subject: Subject) -> SubjectOut:
        teacher = subject.teacher
        return cls(
            id=subject.id,
            name=subject.name,
            code=subject.code,
            teacher_id=subject.teacher_id,
            teacher_name=teacher.full_name if teacher else None,
            teacher_designation=teacher.designation if teacher else None,
            student_limit=subject.student_limit,
            student_count=subject.student_count,
            seats_available=max(subject.student_limit - subject.student_count, 0),
            classes=[ClassRef.model_validate(c) for c in subject.classes],
            created_at=subject.created_at,
        )
