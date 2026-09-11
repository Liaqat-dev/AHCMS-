"""Field types shared by the people-shaped schemas (students, faculty).

Normalization lives here rather than in each schema so a CNIC means the same
thing everywhere: the unique index across the app is only meaningful if every
writer stores the same 13 digits.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BeforeValidator, StringConstraints

CNIC_DIGITS = 13


def normalize_cnic(value: object) -> str | None:
    """Reduce a CNIC/B-Form to its 13 bare digits.

    People type these as 42101-1234567-1, 4210112345671, or with stray spaces.
    Storing whatever arrived would make the unique index meaningless, so the
    separators are stripped here and formatting is a display concern.
    """
    if value is None or value == "":
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) != CNIC_DIGITS:
        raise ValueError(f"CNIC/B-Form must be {CNIC_DIGITS} digits (dashes optional)")
    return digits


def normalize_cell(value: object) -> str | None:
    if value is None or value == "":
        return None
    cleaned = re.sub(r"[\s\-()]", "", str(value))
    if not re.fullmatch(r"\+?\d{7,15}", cleaned):
        raise ValueError("Cell number must be 7-15 digits, optionally +-prefixed")
    return cleaned


Cnic = Annotated[str | None, BeforeValidator(normalize_cnic)]
CellNo = Annotated[str | None, BeforeValidator(normalize_cell)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
OptionalName = Annotated[
    str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
