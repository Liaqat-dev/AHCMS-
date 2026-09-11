"""Faculty schemas.

Mirrors the student surface deliberately: the same CNIC and cell normalizers,
the same "only a name and an identifier are required, the file is completed
later" shape, and the same ``missing_fields`` readout — a personnel file and an
admission file behave the same way in an office.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.db.models.faculty import Faculty
from app.schemas.fields import CellNo, Cnic, Name

#: Employee numbers are typed from an existing paper record, so the only rule
#: is that they are short and not blank.
EmployeeNo = Field(min_length=1, max_length=32, examples=["EMP-014"])


class FacultyBase(BaseModel):
    designation: str | None = Field(default=None, max_length=64, examples=["Lecturer"])
    qualification: str | None = Field(default=None, max_length=150, examples=["MSc Physics"])
    cnic: Cnic = None
    email: EmailStr | None = None
    cell_no: CellNo = None
    address: str | None = Field(default=None, max_length=1000)
    joined_on: date | None = None
    #: The staff account this person signs in with. What makes "only the
    #: teacher of this subject may enter its marks" answerable.
    user_id: uuid.UUID | None = None


class FacultyCreate(FacultyBase):
    employee_no: str = EmployeeNo
    first_name: Name
    last_name: Name


class FacultyUpdate(FacultyBase):
    employee_no: str | None = Field(default=None, min_length=1, max_length=32)
    first_name: Name | None = None
    last_name: Name | None = None
    is_active: bool | None = None


class FacultyOut(BaseModel):
    id: uuid.UUID
    employee_no: str
    first_name: str
    last_name: str
    full_name: str

    designation: str | None
    qualification: str | None
    cnic: str | None
    email: str | None
    cell_no: str | None
    address: str | None
    joined_on: date | None
    user_id: uuid.UUID | None

    is_active: bool
    #: What still has to be collected before the file is complete.
    missing_fields: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_faculty(cls, member: Faculty) -> FacultyOut:
        return cls(
            id=member.id,
            employee_no=member.employee_no,
            first_name=member.first_name,
            last_name=member.last_name,
            full_name=member.full_name,
            designation=member.designation,
            qualification=member.qualification,
            cnic=member.cnic,
            email=member.email,
            cell_no=member.cell_no,
            address=member.address,
            joined_on=member.joined_on,
            user_id=member.user_id,
            is_active=member.is_active,
            missing_fields=member.missing_fields,
            created_at=member.created_at,
        )
