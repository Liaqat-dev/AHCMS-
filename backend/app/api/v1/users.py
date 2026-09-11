"""User management (admin surface): create users, assign roles, activate/deactivate."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import DBSession, Pagination, require_permissions
from app.core import permissions as perm
from app.schemas.common import Page
from app.schemas.user import RoleAssignment, UserCreate, UserOut, UserUpdate
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(perm.USERS_CREATE))],
)
async def create_user(body: UserCreate, db: DBSession) -> UserOut:
    user = await users_service.create_user(
        db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        role_names=body.roles,
    )
    await db.commit()
    return UserOut.from_user(user)


@router.get(
    "",
    response_model=Page[UserOut],
    dependencies=[Depends(require_permissions(perm.USERS_READ))],
)
async def list_users(pagination: Pagination, db: DBSession) -> Page[UserOut]:
    users, total = await users_service.list_users(
        db, limit=pagination.limit, offset=pagination.offset
    )
    return Page(
        items=[UserOut.from_user(u) for u in users],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/{user_id}",
    response_model=UserOut,
    dependencies=[Depends(require_permissions(perm.USERS_READ))],
)
async def get_user(user_id: uuid.UUID, db: DBSession) -> UserOut:
    return UserOut.from_user(await users_service.get_user(db, user_id))


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    dependencies=[Depends(require_permissions(perm.USERS_UPDATE))],
)
async def update_user(user_id: uuid.UUID, body: UserUpdate, db: DBSession) -> UserOut:
    user = await users_service.update_user(
        db, user_id, full_name=body.full_name, is_active=body.is_active
    )
    await db.commit()
    return UserOut.from_user(user)


@router.put(
    "/{user_id}/roles",
    response_model=UserOut,
    dependencies=[Depends(require_permissions(perm.USERS_UPDATE))],
)
async def set_user_roles(user_id: uuid.UUID, body: RoleAssignment, db: DBSession) -> UserOut:
    user = await users_service.set_user_roles(db, user_id, body.roles)
    await db.commit()
    return UserOut.from_user(user)
