"""Health checks — the one fully-implemented surface in this scaffold.

* ``GET /health``    — liveness (no dependencies).
* ``GET /health/db`` — readiness: verifies Postgres connectivity.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DBSession
from app.core.config import settings
from app.exceptions.errors import ServiceUnavailable
from app.schemas.health import DBHealthStatus, HealthStatus

logger = logging.getLogger("app.health")

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    return HealthStatus(status="ok", version=settings.VERSION)


@router.get("/health/db", response_model=DBHealthStatus)
async def health_db(db: DBSession) -> DBHealthStatus:
    try:
        await db.execute(text("SELECT 1"))
    # OSError covers the failures that never reach the driver — DNS lookup and
    # TCP/TLS errors, which SQLAlchemy does not wrap as SQLAlchemyError. A
    # managed database is reached over the network, so these are the common case
    # for an unreachable host; both mean "not ready", not "server bug".
    except (SQLAlchemyError, OSError) as exc:
        logger.error("Database health check failed: %s", exc)
        raise ServiceUnavailable("Database is not reachable") from exc
    return DBHealthStatus(status="ok", database="ok")
