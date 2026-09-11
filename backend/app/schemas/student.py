"""Student management schemas (staff-facing surface).

The password is write-only: it is accepted on create and on the dedicated reset
endpoint, and never appears in any response. ``roll_no`` is likewise never
accepted — it is allocated from the session (see ``app.services.sessions``).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import inspect
from sqlalchemy.orm.base import NO_VALUE

from app.schemas.fields import CellNo, Cnic, Name, OptionalName


class StudentBase(BaseModel):
    """Every field that is optional at admission and filled in later."""

    b_form_cnic: Cnic = None
    date_of_birth: date | None = None

    father_name: OptionalName = None
    father_cnic: Cnic = None
    mother_name: OptionalName = None
    guardian_cell_no: CellNo = None

    cell_no: CellNo = None
    address: str | None = Field(default=None, max_length=1000)
    province: str | None = Field(default=None, max_length=64)
    domicile_district: str | None = Field(default=None, max_length=100)

    last_school_name: str | None = Field(default=None, max_length=255)
    ssc_roll_no: str | None = Field(default=None, max_length=32)
    ssc_marks_obtained: int | None = Field(default=None, ge=0, le=2000)
    ssc_marks_total: int | None = Field(default=None, ge=1, le=2000)
    ssc_year: int | None = Field(default=None, ge=1950, le=2100)

    email: EmailStr | None = None


class StudentCreate(StudentBase):
    # Admission requires only a name and an intake; the roll number is
    # allocated from the session and is never client-supplied.
    session_id: uuid.UUID
    first_name: Name
    last_name: Name
    # Issued to the student for portal login; optional so a record can be
    # created before credentials are handed out.
    password: str | None = Field(default=None, min_length=8, max_length=128)


class StudentUpdate(StudentBase):
    first_name: Name | None = None
    last_name: Name | None = None
    is_active: bool | None = None


class StudentPasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class StudentSession(BaseModel):
    """The session summary embedded in a student response."""

    id: uuid.UUID
    label: str
    start_year: int
    end_year: int

    model_config = {"from_attributes": True}


class StudentEnrollment(BaseModel):
    """The class a student is in, embedded in a student response.

    Just enough to name it — the subjects live on the enrollment endpoints, so
    a student list does not carry a per-row collection it rarely renders.
    """

    id: uuid.UUID
    class_id: uuid.UUID
    class_name: str
    program_id: uuid.UUID
    program_code: str
    subject_count: int

    model_config = {"from_attributes": True}


class StudentOut(BaseModel):
    id: uuid.UUID
    roll_no: str
    session: StudentSession
    #: Null when the student has not been enrolled in a class yet.
    enrollment: StudentEnrollment | None = None

    first_name: str
    last_name: str
    full_name: str
    b_form_cnic: str | None
    date_of_birth: date | None

    father_name: str | None
    father_cnic: str | None
    mother_name: str | None
    guardian_cell_no: str | None

    cell_no: str | None
    address: str | None
    province: str | None
    domicile_district: str | None

    last_school_name: str | None
    ssc_roll_no: str | None
    ssc_marks_obtained: int | None
    ssc_marks_total: int | None
    ssc_year: int | None
    ssc_percentage: float | None

    email: str | None
    is_active: bool
    # Whether the student can sign in yet; the hash itself is never exposed.
    has_password: bool
    # What still has to be collected before the file is complete.
    missing_fields: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}

    @staticmethod
    def _enrollment(student) -> StudentEnrollment | None:
        """Render the enrollment if it was loaded, else nothing.

        ``Student.enrollment`` is ``lazy="raise"``, so callers that did not ask
        for it (the login path, the portal) pass an object with the attribute
        unloaded; that is a "not asked for", not a "not enrolled".
        """
        enrollment = inspect(student).attrs.enrollment
        if enrollment.loaded_value is NO_VALUE or enrollment.value is None:
            return None
        row = enrollment.value
        return StudentEnrollment(
            id=row.id,
            class_id=row.class_id,
            class_name=row.class_.name,
            program_id=row.class_.program_id,
            program_code=row.class_.program.code,
            subject_count=len(row.subject_links),
        )

    @classmethod
    def from_student(cls, student) -> StudentOut:
        return cls(
            enrollment=cls._enrollment(student),
            id=student.id,
            roll_no=student.roll_no,
            session=StudentSession.model_validate(student.session),
            first_name=student.first_name,
            last_name=student.last_name,
            full_name=student.full_name,
            b_form_cnic=student.b_form_cnic,
            date_of_birth=student.date_of_birth,
            father_name=student.father_name,
            father_cnic=student.father_cnic,
            mother_name=student.mother_name,
            guardian_cell_no=student.guardian_cell_no,
            cell_no=student.cell_no,
            address=student.address,
            province=student.province,
            domicile_district=student.domicile_district,
            last_school_name=student.last_school_name,
            ssc_roll_no=student.ssc_roll_no,
            ssc_marks_obtained=student.ssc_marks_obtained,
            ssc_marks_total=student.ssc_marks_total,
            ssc_year=student.ssc_year,
            ssc_percentage=student.ssc_percentage,
            email=student.email,
            is_active=student.is_active,
            has_password=student.hashed_password is not None,
            missing_fields=student.missing_fields,
            created_at=student.created_at,
        )
