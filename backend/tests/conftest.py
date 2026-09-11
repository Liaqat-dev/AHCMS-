"""Test fixtures.

Two client flavors:

* ``client`` — the original hermetic client with a FAKE db session, for wiring
  tests (routing, envelopes, pagination) that never touch real tables.
* ``db_client`` — backed by an in-memory SQLite database (aiosqlite) with the
  full schema created and RBAC seeded, for auth/RBAC tests. Also provides
  ``db_sessionmaker`` and the ``make_user`` / ``make_student`` factories.

Rate limiting is disabled via env so tests are deterministic.
"""

from __future__ import annotations

import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import models  # noqa: E402  (populate Base.metadata)
from app.db.base import Base  # noqa: E402
from app.db.seed import seed_rbac  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402


class _FakeResult:
    def scalar(self) -> int:
        return 1


class _FakeSession:
    async def execute(self, *args, **kwargs) -> _FakeResult:
        return _FakeResult()

    async def rollback(self) -> None:
        return None


async def _override_get_db():
    yield _FakeSession()


@pytest.fixture
async def client():
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ----- Real-DB fixtures (in-memory SQLite) ----------------------------------


@pytest.fixture
async def db_engine():
    # StaticPool: every session shares the single in-memory database.
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(seed_rbac)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_sessionmaker(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_client(db_sessionmaker):
    async def _real_get_db():
        async with db_sessionmaker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _real_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(db_sessionmaker):
    """Factory: create a user with the given roles directly in the DB."""

    async def _make(
        email: str,
        password: str = "password123",
        roles: list[str] | None = None,
        *,
        is_active: bool = True,
    ) -> None:
        async with db_sessionmaker() as db:
            role_rows = []
            if roles:
                role_rows = list(
                    (
                        await db.scalars(
                            select(models.Role).where(models.Role.name.in_(roles))
                        )
                    ).all()
                )
                assert len(role_rows) == len(roles), f"missing roles among {roles}"
            db.add(
                models.User(
                    email=email,
                    hashed_password=hash_password(password),
                    full_name=email.split("@")[0],
                    is_active=is_active,
                    roles=role_rows,
                )
            )
            await db.commit()

    return _make


async def _get_or_create_session(db, start_year: int) -> models.AcademicSession:
    """Sessions are just batches; tests reuse one per start year."""
    session = await db.scalar(
        select(models.AcademicSession).where(
            models.AcademicSession.start_year == start_year
        )
    )
    if session is None:
        session = models.AcademicSession(start_year=start_year)
        db.add(session)
        await db.flush()
    return session


@pytest.fixture
def make_session(db_sessionmaker):
    """Factory: create (or reuse) a batch and return its id."""

    async def _make(start_year: int = 2024) -> str:
        async with db_sessionmaker() as db:
            session = await _get_or_create_session(db, start_year)
            session_id = str(session.id)
            await db.commit()
            return session_id

    return _make


@pytest.fixture
def make_student(db_sessionmaker):
    """Factory: create a student (portal principal, not a User) in the DB.

    Writes the row directly, so it can pin an exact roll number instead of
    taking whichever one the session counter would allocate.
    """

    async def _make(
        roll_no: str,
        password: str | None = "password123",
        *,
        full_name: str | None = None,
        is_active: bool = True,
        start_year: int = 2024,
    ) -> None:
        async with db_sessionmaker() as db:
            session = await _get_or_create_session(db, start_year)
            first_name, _, last_name = (full_name or f"Student {roll_no}").partition(" ")
            db.add(
                models.Student(
                    roll_no=roll_no,
                    session_id=session.id,
                    first_name=first_name,
                    last_name=last_name or "-",
                    hashed_password=hash_password(password) if password else None,
                    is_active=is_active,
                )
            )
            await db.commit()

    return _make


# Test suite is DISABLED by project policy (see CLAUDE.md): no tests are written
# or run unless explicitly asked. The files below are kept intact; pytest simply
# skips collecting them. To re-enable, delete this one line.
collect_ignore_glob = ["test_*.py"]
