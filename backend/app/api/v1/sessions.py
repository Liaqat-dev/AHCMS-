"""Academic sessions router — student batches.

Reading is broad: ``sessions:read`` ships with the teacher role, since picking
a batch or filtering students by one needs it. Creating a batch is
administrative, so it needs ``sessions:write``, which is seeded only to
``super_admin`` — a teacher gets it only if a super-admin grants it to their
role at runtime.

There is no update endpoint. A session's whole content is its start year, and
that year is embedded in every roll number the batch has issued, so it is
write-once by design.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import DBSession, Pagination, require_permissions
from app.core import permissions as perm
from app.schemas.academic_session import AcademicSessionCreate, AcademicSessionOut
from app.schemas.common import Page
from app.services import sessions as sessions_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=AcademicSessionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(perm.SESSIONS_CREATE))],
)
async def create_session(body: AcademicSessionCreate, db: DBSession) -> AcademicSessionOut:
    session = await sessions_service.create_session(db, start_year=body.start_year)
    await db.commit()
    return AcademicSessionOut.from_session(session)


@router.get(
    "",
    response_model=Page[AcademicSessionOut],
    dependencies=[Depends(require_permissions(perm.SESSIONS_READ))],
)
async def list_sessions(pagination: Pagination, db: DBSession) -> Page[AcademicSessionOut]:
    rows, total = await sessions_service.list_sessions(
        db, limit=pagination.limit, offset=pagination.offset
    )
    return Page(
        items=[AcademicSessionOut.from_session(s, count) for s, count in rows],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/{session_id}",
    response_model=AcademicSessionOut,
    dependencies=[Depends(require_permissions(perm.SESSIONS_READ))],
)
async def get_session(session_id: uuid.UUID, db: DBSession) -> AcademicSessionOut:
    return AcademicSessionOut.from_session(await sessions_service.get_session(db, session_id))
