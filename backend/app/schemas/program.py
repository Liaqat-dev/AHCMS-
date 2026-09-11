"""Program schemas.

The code is normalized to upper case on the way in, so "eng", "Eng" and "ENG"
are the same program and the unique constraint actually means something. It is
letters only: a code appears inside composed identifiers, where digits and
punctuation would be ambiguous.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models.program import PROGRAM_CODE_LENGTH, Program

#: Shared constraints for the short form, spelled once. The pattern doubles as
#: the length check so an over-long code fails with one clear message.
_CODE_RULES: dict = {
    "min_length": PROGRAM_CODE_LENGTH,
    "max_length": PROGRAM_CODE_LENGTH,
    "pattern": rf"^[A-Za-z]{{{PROGRAM_CODE_LENGTH}}}$",
    "description": "Three-letter short form, e.g. ENG",
    "examples": ["ENG"],
}


class _ProgramBase(BaseModel):
    """Normalization shared by create and update.

    On the update model both fields are optional, so a validator can also be
    handed an explicit ``null``. That is a client mistake rather than "leave it
    alone" — neither column is nullable — so it is rejected as a 422 instead of
    reaching the service as a None to filter out later.
    """

    @field_validator("name", "code", check_fields=False)
    @classmethod
    def _not_null(cls, value: str | None) -> str:
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


class ProgramCreate(_ProgramBase):
    name: str = Field(min_length=1, max_length=150, examples=["Engineering"])
    code: str = Field(**_CODE_RULES)


class ProgramUpdate(_ProgramBase):
    # Both optional: PATCH may change one without restating the other. Omitted
    # is not the same as null here — see `exclude_unset` in the router.
    name: str | None = Field(default=None, min_length=1, max_length=150)
    code: str | None = Field(default=None, **_CODE_RULES)


class ProgramOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    created_by_id: uuid.UUID | None
    #: Denormalized for display, so a list page need not resolve staff ids
    #: itself. Null when the account was deleted or never recorded.
    created_by_name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_program(cls, program: Program) -> ProgramOut:
        creator = program.created_by
        return cls(
            id=program.id,
            name=program.name,
            code=program.code,
            created_by_id=program.created_by_id,
            created_by_name=(creator.full_name or creator.email) if creator else None,
            created_at=program.created_at,
        )
