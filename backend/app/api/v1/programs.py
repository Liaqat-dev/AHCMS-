"""Programs router — the courses of study students are admitted to.

``programs:read`` ships with the teacher role, since naming a program comes up
wherever students or classes are listed. Creating, renaming and deleting need
``programs:write``, seeded only to ``super_admin``: the three-letter code is a
short form other records quote, so changing it is an administrative act.

``created_by`` is recorded from the caller's token, never taken from the body —
a client must not be able to attribute a program to somebody else.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import AuthContext, DBSession, Pagination, require_permissions
from app.core import permissions as perm
from app.schemas.common import Page
from app.schemas.program import ProgramCreate, ProgramOut, ProgramUpdate
from app.services import programs as programs_service

router = APIRouter(prefix="/programs", tags=["programs"])


@router.post("", response_model=ProgramOut, status_code=status.HTTP_201_CREATED)
async def create_program(
    body: ProgramCreate,
    db: DBSession,
    auth: Annotated[AuthContext, Depends(require_permissions(perm.PROGRAMS_CREATE))],
) -> ProgramOut:
    program = await programs_service.create_program(
        db, name=body.name, code=body.code, created_by_id=auth.user.id
    )
    await db.commit()
    return ProgramOut.from_program(program)


@router.get(
    "",
    response_model=Page[ProgramOut],
    dependencies=[Depends(require_permissions(perm.PROGRAMS_READ))],
)
async def list_programs(
    pagination: Pagination,
    db: DBSession,
    q: Annotated[str | None, Query(max_length=100, description="Name or code")] = None,
) -> Page[ProgramOut]:
    programs, total = await programs_service.list_programs(
        db, limit=pagination.limit, offset=pagination.offset, q=q
    )
    return Page(
        items=[ProgramOut.from_program(p) for p in programs],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/{program_id}",
    response_model=ProgramOut,
    dependencies=[Depends(require_permissions(perm.PROGRAMS_READ))],
)
async def get_program(program_id: uuid.UUID, db: DBSession) -> ProgramOut:
    return ProgramOut.from_program(await programs_service.get_program(db, program_id))


@router.patch(
    "/{program_id}",
    response_model=ProgramOut,
    dependencies=[Depends(require_permissions(perm.PROGRAMS_UPDATE))],
)
async def update_program(program_id: uuid.UUID, body: ProgramUpdate, db: DBSession) -> ProgramOut:
    # exclude_unset so an omitted field stays as it is, rather than being
    # nulled out by the schema's default.
    program = await programs_service.update_program(
        db, program_id, body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return ProgramOut.from_program(program)


@router.delete(
    "/{program_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(perm.PROGRAMS_DELETE))],
)
async def delete_program(program_id: uuid.UUID, db: DBSession) -> None:
    await programs_service.delete_program(db, program_id)
    await db.commit()
