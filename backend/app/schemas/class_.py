"""Class schemas.

A class is a name plus the program it belongs to. The name is trimmed and must
be unique within that program — see ``app.db.models.class_``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models.class_ import Class

#: Shared constraints for the class name, spelled once.
_NAME_RULES: dict = {"min_length": 1, "max_length": 150, "examples": ["ENG-1A"]}


class _ClassBase(BaseModel):
    @field_validator("name", check_fields=False)
    @classmethod
    def _trim(cls, value: str | None) -> str:
        # On the update model the field is optional, so an explicit `null` can
        # arrive here. The column is not nullable, so that is a client mistake
        # rather than "leave it alone" — reject it instead of letting it reach
        # the service as a None to filter out.
        if value is None:
            raise ValueError("must not be null; omit the field to leave it unchanged")
        # min_length runs before this, so a name of pure whitespace gets this
        # far; reject it rather than storing "".
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("must not be blank")
        return trimmed


class ClassCreate(_ClassBase):
    name: str = Field(**_NAME_RULES)
    program_id: uuid.UUID


class ClassUpdate(_ClassBase):
    # Both optional: PATCH may rename a class without restating its program, or
    # move it to another program without restating the name.
    name: str | None = Field(default=None, **_NAME_RULES)
    program_id: uuid.UUID | None = None


class ClassOut(BaseModel):
    id: uuid.UUID
    name: str
    program_id: uuid.UUID
    #: Denormalized for display, so a list page need not resolve program ids
    #: itself. The program is required, so these are never null.
    program_name: str
    program_code: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_class(cls, class_: Class) -> ClassOut:
        return cls(
            id=class_.id,
            name=class_.name,
            program_id=class_.program_id,
            program_name=class_.program.name,
            program_code=class_.program.code,
            created_at=class_.created_at,
        )
