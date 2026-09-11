"""Faculty router — the college's teaching and support staff.

A personnel register, not an account system: faculty are not ``User`` rows and
hold no permissions. Somebody who both teaches and administers the system has
two records, because the two facts are independent.

Guarded by ``faculty:read`` / ``faculty:write``. Reading ships with the teacher
role — a staff room list is not privileged — while writing is seeded only to
``super_admin``.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DBSession, Pagination, require_permissions
from app.core import permissions as perm
from app.schemas.common import Page
from app.schemas.faculty import FacultyCreate, FacultyOut, FacultyUpdate
from app.services import faculty as faculty_service

router = APIRouter(prefix="/faculty", tags=["faculty"])


@router.post(
    "",
    response_model=FacultyOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(perm.FACULTY_CREATE))],
)
async def create_faculty(body: FacultyCreate, db: DBSession) -> FacultyOut:
    payload = body.model_dump()
    member = await faculty_service.create_member(
        db,
        employee_no=payload.pop("employee_no"),
        first_name=payload.pop("first_name"),
        last_name=payload.pop("last_name"),
        **payload,
    )
    await db.commit()
    return FacultyOut.from_faculty(member)


@router.get(
    "",
    response_model=Page[FacultyOut],
    dependencies=[Depends(require_permissions(perm.FACULTY_READ))],
)
async def list_faculty(
    pagination: Pagination,
    db: DBSession,
    q: Annotated[
        str | None, Query(max_length=100, description="Employee no, name, designation or CNIC")
    ] = None,
    is_active: Annotated[
        bool | None, Query(description="Only current or only former staff")
    ] = None,
) -> Page[FacultyOut]:
    members, total = await faculty_service.list_members(
        db, limit=pagination.limit, offset=pagination.offset, q=q, is_active=is_active
    )
    return Page(
        items=[FacultyOut.from_faculty(m) for m in members],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/{faculty_id}",
    response_model=FacultyOut,
    dependencies=[Depends(require_permissions(perm.FACULTY_READ))],
)
async def get_faculty(faculty_id: uuid.UUID, db: DBSession) -> FacultyOut:
    return FacultyOut.from_faculty(await faculty_service.get_member(db, faculty_id))


@router.patch(
    "/{faculty_id}",
    response_model=FacultyOut,
    dependencies=[Depends(require_permissions(perm.FACULTY_UPDATE))],
)
async def update_faculty(
    faculty_id: uuid.UUID, body: FacultyUpdate, db: DBSession
) -> FacultyOut:
    # exclude_unset so an omitted field stays as it is, rather than being
    # nulled out by the schema's default.
    member = await faculty_service.update_member(
        db, faculty_id, body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return FacultyOut.from_faculty(member)


@router.delete(
    "/{faculty_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(perm.FACULTY_DELETE))],
)
async def delete_faculty(faculty_id: uuid.UUID, db: DBSession) -> None:
    """Remove the record.

    Marking someone inactive is usually what is wanted — a former colleague
    should still be nameable on old records — so this is the rarer action.
    """
    await faculty_service.delete_member(db, faculty_id)
    await db.commit()
