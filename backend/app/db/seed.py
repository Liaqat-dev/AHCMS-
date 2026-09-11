"""Idempotent RBAC seed: roles, the permission catalog, and default grants.

Runs on a **sync** connection so the same code serves the Alembic migration,
the test fixtures (via ``conn.run_sync``), and the super-admin CLI.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Connection, insert, select

from app.core.permissions import (
    ALL_ROLES,
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSION_DESCRIPTIONS,
    ROLE_DESCRIPTIONS,
    SYSTEM_ROLES,
)
from app.db.models.rbac import Permission, Role, role_permissions


def seed_rbac(conn: Connection) -> None:
    """Insert any missing roles/permissions and the default role grants."""
    existing_roles = dict(conn.execute(select(Role.name, Role.id)).tuples().all())
    for name in ALL_ROLES:
        if name not in existing_roles:
            role_id = uuid.uuid4()
            conn.execute(
                insert(Role).values(
                    id=role_id,
                    name=name,
                    description=ROLE_DESCRIPTIONS[name],
                    is_system=name in SYSTEM_ROLES,
                )
            )
            existing_roles[name] = role_id

    existing_perms = dict(conn.execute(select(Permission.code, Permission.id)).tuples().all())
    for code, description in PERMISSION_DESCRIPTIONS.items():
        if code not in existing_perms:
            perm_id = uuid.uuid4()
            conn.execute(insert(Permission).values(id=perm_id, code=code, description=description))
            existing_perms[code] = perm_id

    existing_grants = set(
        conn.execute(select(role_permissions.c.role_id, role_permissions.c.permission_id))
        .tuples()
        .all()
    )
    for role_name, codes in DEFAULT_ROLE_PERMISSIONS.items():
        role_id = existing_roles[role_name]
        for code in codes:
            pair = (role_id, existing_perms[code])
            if pair not in existing_grants:
                conn.execute(
                    role_permissions.insert().values(role_id=pair[0], permission_id=pair[1])
                )
