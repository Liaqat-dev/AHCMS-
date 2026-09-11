"""Health-check response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str = "ok"
    version: str


class DBHealthStatus(BaseModel):
    status: str = "ok"
    database: str
