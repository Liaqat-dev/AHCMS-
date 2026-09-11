"""Academic session schemas — a batch identifier, nothing more.

A session is created and then read. There is nothing to edit: the start year is
its whole content, and it is baked into every roll number the batch has already
issued, so changing it would leave those students carrying a number that no
longer matches their batch.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AcademicSessionCreate(BaseModel):
    # `end_year` is not accepted: it is always start_year + 2, and taking it
    # from the client would just be a second source of truth to disagree with.
    start_year: int = Field(ge=2000, le=2100)


class AcademicSessionOut(BaseModel):
    id: uuid.UUID
    start_year: int
    end_year: int
    label: str
    student_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_session(cls, session, student_count: int = 0) -> AcademicSessionOut:
        return cls(
            id=session.id,
            start_year=session.start_year,
            end_year=session.end_year,
            label=session.label,
            student_count=student_count,
            created_at=session.created_at,
        )
