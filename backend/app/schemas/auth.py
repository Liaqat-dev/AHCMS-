"""Auth request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Staff login. Students use StudentLoginRequest instead."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class StudentLoginRequest(BaseModel):
    """Student portal login — roll number and password, nothing else."""

    roll_no: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=8, max_length=128)


class AuthenticatedUser(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    roles: list[str]
    permissions: list[str]

    model_config = {"from_attributes": True}


class AuthenticatedStudent(BaseModel):
    """The student portal principal. Deliberately carries no roles/permissions."""

    id: uuid.UUID
    roll_no: str
    full_name: str
    email: str | None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthenticatedUser


class StudentTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    student: AuthenticatedStudent


class SessionInfo(BaseModel):
    id: uuid.UUID
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    expires_at: datetime
    current: bool = False

    model_config = {"from_attributes": True}
