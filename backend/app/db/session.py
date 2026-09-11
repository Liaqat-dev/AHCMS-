"""Async database engine, session factory, and the ``get_db`` dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _engine_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "echo": settings.DB_ECHO,
        # Managed Postgres closes idle connections (Neon after ~5 minutes) and
        # suspends idle projects, so verify and rotate pooled connections.
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    # asyncpg does not accept ``sslmode`` in the URL — pass TLS via connect_args.
    # Managed Postgres (e.g. Neon) requires this; local Postgres does not.
    if settings.db_requires_ssl:
        kwargs["connect_args"] = {"ssl": True}
    return kwargs


engine = create_async_engine(settings.sqlalchemy_database_uri, **_engine_kwargs())

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a session with commit-safe teardown."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
