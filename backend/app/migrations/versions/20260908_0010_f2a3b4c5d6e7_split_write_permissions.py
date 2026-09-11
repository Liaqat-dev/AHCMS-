"""Split every :write permission into :create, :update and :delete

``resource:write`` meant create *and* update *and* delete in one grant. That
put "correct a student's mark" and "throw away a whole day's register" behind
the same permission, which is not a distinction an administrator should have to
give up.

Each ``:write`` becomes the actions its endpoints actually expose. A code is
minted only where an endpoint backs it: there is no ``DELETE /students`` or
``DELETE /users`` (both are deactivated instead), and an academic session is
write-once, so ``students:delete``, ``users:delete``, ``sessions:update`` and
``sessions:delete`` do not exist. A permission that can be granted but does
nothing implies a control that is not there.

**No role loses access.** Every role holding ``x:write`` is granted each new
action for that resource before the old code is removed, so behaviour is
identical the moment this runs. Narrowing a role — revoking
``attendance:delete`` from ``teacher``, say — is then a click in the roles
grid, which is the point of the change.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-08
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: resource -> the actions that have an endpoint behind them.
_SPLIT: dict[str, tuple[str, ...]] = {
    "students": ("create", "update"),
    "faculty": ("create", "update", "delete"),
    "enrollments": ("create", "update", "delete"),
    "users": ("create", "update"),
    "roles": ("create", "update", "delete"),
    "sessions": ("create",),
    "programs": ("create", "update", "delete"),
    "classes": ("create", "update", "delete"),
    "subjects": ("create", "update", "delete"),
    "attendance": ("create", "update", "delete"),
}

_DESCRIPTIONS: dict[str, str] = {
    "students:create": "Admit students",
    "students:update": "Edit students and set their portal passwords",
    "faculty:create": "Add faculty",
    "faculty:update": "Edit faculty",
    "faculty:delete": "Delete faculty records",
    "enrollments:create": "Enrol students in a class",
    "enrollments:update": "Move a student's class and change their subjects",
    "enrollments:delete": "Unenroll students",
    "users:create": "Create staff accounts",
    "users:update": "Edit staff accounts and assign roles",
    "roles:create": "Create roles",
    "roles:update": "Rename roles and change the permissions they carry",
    "roles:delete": "Delete roles",
    "sessions:create": "Create academic sessions (student batches)",
    "programs:create": "Create programs",
    "programs:update": "Edit programs",
    "programs:delete": "Delete programs",
    "classes:create": "Create classes",
    "classes:update": "Edit classes",
    "classes:delete": "Delete classes",
    "subjects:create": "Create subjects",
    "subjects:update": "Edit subjects and the classes they run in",
    "subjects:delete": "Delete subjects",
    "attendance:create": "Open attendance registers",
    "attendance:update": "Mark students on a register",
    "attendance:delete": "Delete attendance registers",
}

_OLD_DESCRIPTIONS: dict[str, str] = {
    "students:write": "Create/update students and set their portal passwords",
    "faculty:write": "Create/update/delete faculty",
    "enrollments:write": "Create/update/delete enrollments",
    "users:write": "Create staff accounts and assign roles",
    "roles:write": "Create roles and change the permissions they carry",
    "sessions:write": "Create academic sessions (student batches)",
    "programs:write": "Create/update/delete programs",
    "classes:write": "Create/update/delete classes",
    "subjects:write": "Create/update/delete subjects and the classes they run in",
    "attendance:write": "Open attendance registers and mark students",
}

_INSERT_PERMISSION = sa.text(
    "INSERT INTO permissions (id, code, description) VALUES (:id, :code, :description)"
    " ON CONFLICT (code) DO NOTHING"
)
#: Grant a code to every role that already holds another one.
_CARRY_GRANT = sa.text(
    "INSERT INTO role_permissions (role_id, permission_id)"
    " SELECT rp.role_id, (SELECT id FROM permissions WHERE code = :new)"
    " FROM role_permissions rp"
    " JOIN permissions p ON p.id = rp.permission_id"
    " WHERE p.code = :old"
    " AND NOT EXISTS ("
    "   SELECT 1 FROM role_permissions x"
    "   WHERE x.role_id = rp.role_id"
    "     AND x.permission_id = (SELECT id FROM permissions WHERE code = :new)"
    " )"
)
_DROP_CODE = sa.text(
    "DELETE FROM role_permissions WHERE permission_id ="
    " (SELECT id FROM permissions WHERE code = :code)"
)
_DELETE_PERMISSION = sa.text("DELETE FROM permissions WHERE code = :code")


def upgrade() -> None:
    bind = op.get_bind()

    for resource, actions in _SPLIT.items():
        old = f"{resource}:write"
        for action in actions:
            new = f"{resource}:{action}"
            bind.execute(
                _INSERT_PERMISSION,
                {"id": uuid.uuid4(), "code": new, "description": _DESCRIPTIONS[new]},
            )
            # Carry the existing grant across before the old code goes.
            bind.execute(_CARRY_GRANT, {"new": new, "old": old})

        bind.execute(_DROP_CODE, {"code": old})
        bind.execute(_DELETE_PERMISSION, {"code": old})


def downgrade() -> None:
    bind = op.get_bind()

    for resource, actions in _SPLIT.items():
        old = f"{resource}:write"
        bind.execute(
            _INSERT_PERMISSION,
            {"id": uuid.uuid4(), "code": old, "description": _OLD_DESCRIPTIONS[old]},
        )
        # A role that held any of the split actions gets the coarse code back.
        for action in actions:
            bind.execute(_CARRY_GRANT, {"new": old, "old": f"{resource}:{action}"})

        for action in actions:
            new = f"{resource}:{action}"
            bind.execute(_DROP_CODE, {"code": new})
            bind.execute(_DELETE_PERMISSION, {"code": new})
