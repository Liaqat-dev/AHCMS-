"""Admin user & RBAC management: create users, assign roles, edit role grants."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import SYSTEM_ROLES
from app.core.security import hash_password
from app.db.models import Permission, Role, User, user_roles
from app.exceptions.errors import BadRequest, Conflict, NotFound


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFound("User not found")
    return user


async def list_users(db: AsyncSession, *, limit: int, offset: int) -> tuple[list[User], int]:
    total = await db.scalar(select(func.count()).select_from(User)) or 0
    users = (
        await db.scalars(select(User).order_by(User.created_at).limit(limit).offset(offset))
    ).all()
    return list(users), total


async def _resolve_roles(db: AsyncSession, role_names: list[str]) -> list[Role]:
    if not role_names:
        return []
    roles = (await db.scalars(select(Role).where(Role.name.in_(role_names)))).all()
    missing = set(role_names) - {r.name for r in roles}
    if missing:
        raise NotFound(f"Unknown role(s): {', '.join(sorted(missing))}")
    return list(roles)


async def create_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str | None,
    role_names: list[str],
) -> User:
    email = email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise Conflict("A user with this email already exists")
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        roles=await _resolve_roles(db, role_names),
    )
    db.add(user)
    await db.flush()
    return user


async def set_user_roles(db: AsyncSession, user_id: uuid.UUID, role_names: list[str]) -> User:
    user = await get_user(db, user_id)
    user.roles = await _resolve_roles(db, role_names)
    await db.flush()
    return user


async def update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    full_name: str | None = None,
    is_active: bool | None = None,
) -> User:
    user = await get_user(db, user_id)
    if full_name is not None:
        user.full_name = full_name
    if is_active is not None:
        user.is_active = is_active
    await db.flush()
    return user


# ----- Roles / permissions ---------------------------------------------------


async def list_roles(db: AsyncSession) -> list[Role]:
    return list((await db.scalars(select(Role).order_by(Role.name))).all())


async def list_permissions(db: AsyncSession) -> list[Permission]:
    return list((await db.scalars(select(Permission).order_by(Permission.code))).all())


async def _get_role(db: AsyncSession, role_id: uuid.UUID) -> Role:
    role = await db.get(Role, role_id)
    if role is None:
        raise NotFound("Role not found")
    return role


def _reject_system_role(role: Role, action: str) -> None:
    """System roles are immutable so RBAC administration cannot be locked out.

    Without this a super-admin could revoke ``roles:write`` from the only role
    that grants it, leaving no account able to grant it back.
    """
    if role.is_system or role.name in SYSTEM_ROLES:
        raise BadRequest(f"The {role.name!r} role is a system role and cannot be {action}")


async def _resolve_permissions(db: AsyncSession, codes: list[str]) -> list[Permission]:
    if not codes:
        return []
    perms = (await db.scalars(select(Permission).where(Permission.code.in_(codes)))).all()
    missing = set(codes) - {p.code for p in perms}
    if missing:
        raise NotFound(f"Unknown permission(s): {', '.join(sorted(missing))}")
    return list(perms)


async def create_role(
    db: AsyncSession, *, name: str, description: str | None, permission_codes: list[str]
) -> Role:
    """Create a new role at runtime, with its initial permission set."""
    name = name.strip()
    if await db.scalar(select(Role.id).where(Role.name == name)):
        raise Conflict("A role with this name already exists")
    role = Role(
        name=name,
        description=description,
        is_system=False,
        permissions=await _resolve_permissions(db, permission_codes),
    )
    db.add(role)
    await db.flush()
    return role


async def update_role(
    db: AsyncSession,
    role_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Role:
    role = await _get_role(db, role_id)
    if name is not None and name.strip() != role.name:
        _reject_system_role(role, "renamed")
        name = name.strip()
        if await db.scalar(select(Role.id).where(Role.name == name, Role.id != role.id)):
            raise Conflict("A role with this name already exists")
        role.name = name
    if description is not None:
        role.description = description
    await db.flush()
    return role


async def delete_role(db: AsyncSession, role_id: uuid.UUID) -> None:
    """Delete a role. Refused for system roles and roles still assigned."""
    role = await _get_role(db, role_id)
    _reject_system_role(role, "deleted")
    holders = (
        await db.scalar(
            select(func.count()).select_from(user_roles).where(user_roles.c.role_id == role.id)
        )
        or 0
    )
    if holders:
        raise Conflict(f"{holders} user(s) still hold this role; reassign them before deleting it")
    await db.delete(role)
    await db.flush()


async def set_role_permissions(
    db: AsyncSession, role_id: uuid.UUID, permission_codes: list[str]
) -> Role:
    """Replace a role's permission set — the dynamic-RBAC edit surface."""
    role = await _get_role(db, role_id)
    _reject_system_role(role, "edited")
    role.permissions = await _resolve_permissions(db, permission_codes)
    await db.flush()
    return role
