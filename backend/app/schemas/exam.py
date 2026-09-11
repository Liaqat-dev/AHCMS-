"""Exam schemas.

An exam reads as "this class, on this date, these papers", so the response
embeds the class and every paper with its subject and teacher. Marks are
fetched per paper, because that is the unit a teacher is allowed to touch.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator

from app.db.models.exam import DEFAULT_TOTAL_MARKS, EXAM_SCOPES, Exam, ExamSubject

#: Mirrors the model's CHECK, so an unknown scope is a 422 from FastAPI itself.
ExamScope = Literal["subject", "class"]

if set(get_args(ExamScope)) != set(EXAM_SCOPES):  # pragma: no cover
    raise RuntimeError("ExamScope is out of step with the model's scope list")

_TOTAL_RULES: dict = {"ge": 1, "le": 1000, "examples": [DEFAULT_TOTAL_MARKS]}


class ExamCreate(BaseModel):
    class_id: uuid.UUID
    title: str = Field(min_length=1, max_length=150, examples=["Mid-term"])
    date: date_type
    #: "subject" examines one; "class" examines everything the class runs.
    scope: ExamScope = "class"
    #: Required when scope is "subject", ignored otherwise.
    subject_id: uuid.UUID | None = None
    #: Applied to every paper. Per-paper totals are edited afterwards.
    total_marks: int = Field(default=DEFAULT_TOTAL_MARKS, **_TOTAL_RULES)

    @field_validator("title")
    @classmethod
    def _trim(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("must not be blank")
        return trimmed


class ExamUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    date: date_type | None = None


class PaperTotalUpdate(BaseModel):
    total_marks: int = Field(**_TOTAL_RULES)


class MarkIn(BaseModel):
    student_id: uuid.UUID
    #: Null with `is_absent` false clears the mark back to "not entered".
    obtained: int | None = Field(default=None, ge=0, le=1000)
    is_absent: bool = False


class MarkBatch(BaseModel):
    marks: list[MarkIn]


class ClassRef(BaseModel):
    id: uuid.UUID
    name: str
    program_id: uuid.UUID
    program_code: str


class PaperOut(BaseModel):
    """One subject within an exam."""

    id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str
    subject_code: str
    total_marks: int
    teacher_id: uuid.UUID | None
    teacher_name: str | None
    #: How many students have a mark recorded, for progress at a glance.
    marked: int

    @classmethod
    def from_paper(cls, paper: ExamSubject, marked: int) -> PaperOut:
        teacher = paper.subject.teacher
        return cls(
            id=paper.id,
            subject_id=paper.subject_id,
            subject_name=paper.subject.name,
            subject_code=paper.subject.code,
            total_marks=paper.total_marks,
            teacher_id=paper.subject.teacher_id,
            teacher_name=teacher.full_name if teacher else None,
            marked=marked,
        )


class ExamOut(BaseModel):
    id: uuid.UUID
    title: str
    date: date_type
    scope: ExamScope
    class_: ClassRef = Field(serialization_alias="class", validation_alias="class")
    papers: list[PaperOut]
    created_by_id: uuid.UUID | None
    created_at: datetime

    model_config = {"populate_by_name": True}

    @classmethod
    def from_exam(cls, exam: Exam, counts: dict[uuid.UUID, int] | None = None) -> ExamOut:
        marked = counts or {}
        return cls(
            id=exam.id,
            title=exam.title,
            date=exam.date,
            scope=exam.scope,
            papers=[PaperOut.from_paper(p, marked.get(p.id, 0)) for p in exam.subjects],
            created_by_id=exam.created_by_id,
            created_at=exam.created_at,
            **{
                "class": ClassRef(
                    id=exam.class_.id,
                    name=exam.class_.name,
                    program_id=exam.class_.program_id,
                    program_code=exam.class_.program.code,
                )
            },
        )


class StudentRef(BaseModel):
    id: uuid.UUID
    roll_no: str
    first_name: str
    last_name: str

    model_config = {"from_attributes": True}


class MarkOut(BaseModel):
    student: StudentRef
    #: Null means nobody has entered a mark yet — not a zero.
    obtained: int | None = None
    is_absent: bool = False
    marked_by_id: uuid.UUID | None = None
    marked_at: datetime | None = None


class MarkSheet(BaseModel):
    """One paper with everyone sitting it, in roll-number order."""

    paper: PaperOut
    exam_id: uuid.UUID
    exam_title: str
    date: date_type
    class_name: str
    #: Whether *this* caller may enter marks here — the teacher, or an override.
    can_mark: bool
    marks: list[MarkOut]
