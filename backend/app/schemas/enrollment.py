"""Enrollment schemas.

An enrollment reads as "this student, in this class, taking these subjects", so
the response embeds all three rather than handing back ids to resolve. The
write side stays minimal: ids only.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.enrollment import Enrollment


class EnrollmentCreate(BaseModel):
    student_id: uuid.UUID
    class_id: uuid.UUID
    #: Optional from the start, so admission can be one call. Subjects must be
    #: taught to the chosen class; an empty list means the student takes none.
    subject_ids: list[uuid.UUID] = Field(default_factory=list)


class EnrollmentMove(BaseModel):
    """Move to another class. Drops every subject picked in the old one."""

    class_id: uuid.UUID


class SubjectSelection(BaseModel):
    """The full set of subjects this student takes — this replaces the list."""

    subject_ids: list[uuid.UUID]


class StudentRef(BaseModel):
    id: uuid.UUID
    roll_no: str
    first_name: str
    last_name: str

    model_config = {"from_attributes": True}


class ClassRef(BaseModel):
    id: uuid.UUID
    name: str
    program_id: uuid.UUID
    program_name: str
    program_code: str

    model_config = {"from_attributes": True}


class SubjectRef(BaseModel):
    id: uuid.UUID
    name: str
    code: str

    model_config = {"from_attributes": True}


class EnrollmentOut(BaseModel):
    id: uuid.UUID
    student: StudentRef
    class_: ClassRef = Field(serialization_alias="class", validation_alias="class")
    subjects: list[SubjectRef]
    enrolled_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}

    @classmethod
    def from_enrollment(cls, enrollment: Enrollment) -> EnrollmentOut:
        class_ = enrollment.class_
        return cls(
            id=enrollment.id,
            student=StudentRef.model_validate(enrollment.student),
            # `class` is a Python keyword, so the field is `class_` in code and
            # serialized as "class" — the API says what it means.
            **{
                "class": ClassRef(
                    id=class_.id,
                    name=class_.name,
                    program_id=class_.program_id,
                    program_name=class_.program.name,
                    program_code=class_.program.code,
                )
            },
            subjects=[SubjectRef.model_validate(s) for s in enrollment.subjects],
            enrolled_at=enrollment.enrolled_at,
            created_at=enrollment.created_at,
        )


class EnrollmentMoveOut(BaseModel):
    """A move, plus what it cost: the picks that could not survive it."""

    enrollment: EnrollmentOut
    dropped_subjects: int
