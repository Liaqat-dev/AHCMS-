"""Declarative base for all ORM models.

Kept import-light on purpose (no model imports here) to avoid circular imports.
Alembic and the app register models by importing the ``app.db.models`` package,
which populates ``Base.metadata``.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
