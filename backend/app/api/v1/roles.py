"""Roles & permissions (dynamic RBAC surface).

The permission catalog is fixed. Roles are not: ``super_admin`` creates new
roles here and edits which permissions each one carries, all at runtime.
``roles:write`` is granted only to ``super_admin`` by default.

System roles (``core.permissions.SYSTEM_ROLES``) are immutable — see
``services.users._reject_system_role`` for why.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import DBSession, require_permissions
from app.core import permissions as perm
from app.schemas.user import (
    PermissionAssignment,
    PermissionOut,
    RoleCreate,
    RoleOut,
    RoleUpdate,
)
from app.services import users as users_service

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get(
    "",
    response_model=list[RoleOut],
    dependencies=[Depends(require_permissions(perm.ROLES_READ))],
)
async def list_roles(db: DBSession) -> list[RoleOut]:
    return [RoleOut.from_role(r) for r in await users_service.list_roles(db)]


@router.post(
    "",
    response_model=RoleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(perm.ROLES_CREATE))],
)
async def create_role(body: RoleCreate, db: DBSession) -> RoleOut:
    role = await users_service.create_role(
        db,
        name=body.name,
        description=body.description,
        permission_codes=body.permissions,
    )
    await db.commit()
    return RoleOut.from_role(role)


@router.get(
    "/permissions",
    response_model=list[PermissionOut],
    dependencies=[Depends(require_permissions(perm.ROLES_READ))],
)
async def list_permissions(db: DBSession) -> list[PermissionOut]:
    return [PermissionOut.model_validate(p) for p in await users_service.list_permissions(db)]


@router.patch(
    "/{role_id}",
    response_model=RoleOut,
    dependencies=[Depends(require_permissions(perm.ROLES_UPDATE))],
)
async def update_role(role_id: uuid.UUID, body: RoleUpdate, db: DBSession) -> RoleOut:
    role = await users_service.update_role(
        db, role_id, name=body.name, description=body.description
    )
    await db.commit()
    return RoleOut.from_role(role)


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions(perm.ROLES_DELETE))],
)
async def delete_role(role_id: uuid.UUID, db: DBSession) -> None:
    await users_service.delete_role(db, role_id)
    await db.commit()


@router.put(
    "/{role_id}/permissions",
    response_model=RoleOut,
    dependencies=[Depends(require_permissions(perm.ROLES_UPDATE))],
)
async def set_role_permissions(
    role_id: uuid.UUID, body: PermissionAssignment, db: DBSession
) -> RoleOut:
    role = await users_service.set_role_permissions(db, role_id, body.permissions)
    await db.commit()
    return RoleOut.from_role(role)
