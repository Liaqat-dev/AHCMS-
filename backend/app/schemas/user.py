"""User & RBAC management schemas (admin surface)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    roles: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class RoleAssignment(BaseModel):
    roles: list[str]


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    is_active: bool
    roles: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_user(cls, user) -> UserOut:
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            roles=user.role_names,
            created_at=user.created_at,
        )


class PermissionOut(BaseModel):
    id: uuid.UUID
    code: str
    description: str | None

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    description: str | None = Field(default=None, max_length=255)


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    permissions: list[str]
    # System roles cannot be renamed, deleted, or have permissions edited.
    is_system: bool

    model_config = {"from_attributes": True}

    @classmethod
    def from_role(cls, role) -> RoleOut:
        return cls(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=sorted(role.permission_codes),
            is_system=role.is_system,
        )


class PermissionAssignment(BaseModel):
    permissions: list[str]
