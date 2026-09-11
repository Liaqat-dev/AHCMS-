"""Classes router — the teaching groups inside a program.

``classes:read`` ships with the teacher role; creating, renaming, moving and
deleting need ``classes:write``, seeded only to ``super_admin``.

A class always belongs to a program, so ``GET /classes?program_id=...`` is the
way to list one program's classes; the program is embedded in every response
rather than left as a bare id for the client to resolve.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DBSession, Pagination, require_permissions
from app.core import permissions as perm
from app.schemas.attendance import AttendanceOut, sheet_of
from app.schemas.class_ import ClassCreate, ClassOut, ClassUpdate
from app.schemas.common import Page
from app.services import attendance as attendance_service
from app.services import classes as classes_service

router = APIRouter(prefix="/classes", tags=["classes"])


@router.post(
    "",
    response_model=ClassOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(perm.CLASSES_CREATE))],
)
async def create_class(body: ClassCreate, db: DBSession) -> ClassOut:
    class_ = await classes_service.create_class(db, name=body.name, program_id=body.program_id)
    await db.commit()
    return ClassOut.from_class(class_)


@router.get(
    "",
    response_model=Page[ClassOut],
    dependencies=[Depends(require_permissions(perm.CLASSES_READ))],
)
async def list_classes(
    pagination: Pagination,
    db: DBSession,
    program_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100, description="Class name")] = None,
) -> Page[ClassOut]:
    classes, total = await classes_service.list_classes(
        db,
        limit=pagination.limit,
        offset=pagination.offset,
        program_id=program_id,
        q=q,
    )
    return Page(
        items=[ClassOut.from_class(c) for c in classes],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/{class_id}",
    response_model=ClassOut,
    dependencies=[Depends(require_permissions(perm.CLASSES_READ))],
)
async def get_class(class_id: uuid.UUID, db: DBSession) -> ClassOut:
    return ClassOut.from_class(await classes_service.get_class(db, class_id))


@router.get(
    "/{class_id}/attendance/{on}",
    response_model=AttendanceOut,
    dependencies=[Depends(require_permissions(perm.ATTENDANCE_READ))],
)
async def get_class_attendance(
    class_id: uuid.UUID, on: date_type, db: DBSession
) -> AttendanceOut:
    """The register for one class on one date — how a UI actually asks for it.

    404 when the class did not meet that day; there is no empty-sheet fiction.
    """
    sheet = await attendance_service.get_sheet_for(db, class_id, on)
    return sheet_of(sheet, await attendance_service.roster(db, class_id, on))


@router.patch(
    "/{class_id}",
    response_model=ClassOut,
    dependencies=[Depends(require_permissions(perm.CLASSES_UPDATE))],
)
async def update_class(class_id: uuid.UUID, body: ClassUpdate, db: DBSession) -> ClassOut:
    # exclude_unset so an omitted field stays as it is, rather than being
    # nulled out by the schema's default.
    class_ = await classes_service.update_class(db, class_id, body.model_dump(exclude_unset=True))
    await db.commit()
    return ClassOut.from_class(class_)


@router.delete(
    "/{class_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(perm.CLASSES_DELETE))],
)
async def delete_class(class_id: uuid.UUID, db: DBSession) -> None:
    await classes_service.delete_class(db, class_id)
    await db.commit()
