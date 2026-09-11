"""Subjects router — taught subjects, shared across classes.

A subject is many-to-many with classes: one class runs several subjects, and a
subject like "Mathematics I" is taught to several classes rather than being
duplicated for each. The link is edited from the subject's side
(``PUT /subjects/{id}/classes`` replaces the whole set, the way the roles
router replaces a role's permissions); ``GET /subjects?class_id=...`` reads it
from the class's side.

``teacher_id`` names a ``faculty`` row, not a staff ``User``: teaching is a
fact about a person on the college's books, and plenty of them never sign in.
It is optional, because a subject is usually created before the timetable is
settled.

``student_limit`` (default 30) caps enrollment; ``student_count`` is read-only
here and maintained by ``app.services.capacity`` as students enroll. Detaching
a class whose students already take this subject is a 409, as is deleting a
subject anybody has taken up.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DBSession, Pagination, require_permissions
from app.core import permissions as perm
from app.schemas.common import Page
from app.schemas.subject import (
    SubjectClassAssignment,
    SubjectCreate,
    SubjectOut,
    SubjectUpdate,
)
from app.services import subjects as subjects_service

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.post(
    "",
    response_model=SubjectOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(perm.SUBJECTS_CREATE))],
)
async def create_subject(body: SubjectCreate, db: DBSession) -> SubjectOut:
    subject = await subjects_service.create_subject(
        db,
        name=body.name,
        code=body.code,
        student_limit=body.student_limit,
        teacher_id=body.teacher_id,
        class_ids=body.class_ids,
    )
    await db.commit()
    return SubjectOut.from_subject(subject)


@router.get(
    "",
    response_model=Page[SubjectOut],
    dependencies=[Depends(require_permissions(perm.SUBJECTS_READ))],
)
async def list_subjects(
    pagination: Pagination,
    db: DBSession,
    class_id: Annotated[
        uuid.UUID | None, Query(description="Only subjects taught to this class")
    ] = None,
    q: Annotated[str | None, Query(max_length=100, description="Name or code")] = None,
) -> Page[SubjectOut]:
    subjects, total = await subjects_service.list_subjects(
        db,
        limit=pagination.limit,
        offset=pagination.offset,
        class_id=class_id,
        q=q,
    )
    return Page(
        items=[SubjectOut.from_subject(s) for s in subjects],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/{subject_id}",
    response_model=SubjectOut,
    dependencies=[Depends(require_permissions(perm.SUBJECTS_READ))],
)
async def get_subject(subject_id: uuid.UUID, db: DBSession) -> SubjectOut:
    return SubjectOut.from_subject(await subjects_service.get_subject(db, subject_id))


@router.patch(
    "/{subject_id}",
    response_model=SubjectOut,
    dependencies=[Depends(require_permissions(perm.SUBJECTS_UPDATE))],
)
async def update_subject(subject_id: uuid.UUID, body: SubjectUpdate, db: DBSession) -> SubjectOut:
    # exclude_unset so an omitted field stays as it is, rather than being
    # nulled out by the schema's default.
    subject = await subjects_service.update_subject(
        db, subject_id, body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return SubjectOut.from_subject(subject)


@router.put(
    "/{subject_id}/classes",
    response_model=SubjectOut,
    dependencies=[Depends(require_permissions(perm.SUBJECTS_UPDATE))],
)
async def set_subject_classes(
    subject_id: uuid.UUID, body: SubjectClassAssignment, db: DBSession
) -> SubjectOut:
    """Replace the set of classes this subject is taught to."""
    subject = await subjects_service.set_classes(db, subject_id, body.class_ids)
    await db.commit()
    return SubjectOut.from_subject(subject)


@router.delete(
    "/{subject_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(perm.SUBJECTS_DELETE))],
)
async def delete_subject(subject_id: uuid.UUID, db: DBSession) -> None:
    await subjects_service.delete_subject(db, subject_id)
    await db.commit()
