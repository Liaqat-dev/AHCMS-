"""Classes table and its two permissions

A class is a teaching group inside a program: a ``name`` and the ``program_id``
it belongs to. One program has many classes, and the name is unique *within* a
program rather than globally, so two programs can each run a "1st Year"
without one of them having to invent a prefix.

The foreign key is ON DELETE RESTRICT: deleting a program must not silently
take its classes with it. ``services.programs.delete_program`` checks for
classes first and answers 409, so the constraint is a backstop rather than the
usual path.

``classes:read`` is granted to ``teacher`` as well as ``super_admin``;
``classes:write`` goes only to ``super_admin``. As in the previous revisions
the permission rows are inserted inline rather than by importing
``app.db.seed``, so re-running this revision years from now reproduces exactly
these grants.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-08
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PERMISSIONS = (
    ("classes:read", "View classes"),
    ("classes:write", "Create/update/delete classes"),
)
# role name -> permission codes this revision grants it
_GRANTS = {
    "super_admin": ("classes:read", "classes:write"),
    "teacher": ("classes:read",),
}
_CODES = tuple(code for code, _ in _NEW_PERMISSIONS)


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "classes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("program_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["programs.id"],
            name="fk_classes_program_id_programs",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("program_id", "name", name="uq_classes_program_name"),
    )
    op.create_index(op.f("ix_classes_program_id"), "classes", ["program_id"])

    # ----- permissions -------------------------------------------------------
    for code, description in _NEW_PERMISSIONS:
        existing = bind.execute(
            sa.text("SELECT id FROM permissions WHERE code = :code"), {"code": code}
        ).scalar()
        if existing is None:
            bind.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, description)"
                    " VALUES (:id, :code, :description)"
                ),
                {"id": uuid.uuid4(), "code": code, "description": description},
            )

    for role_name, codes in _GRANTS.items():
        role_id = bind.execute(
            sa.text("SELECT id FROM roles WHERE name = :name"), {"name": role_name}
        ).scalar()
        if role_id is None:
            continue
        for code in codes:
            bind.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id)"
                    " SELECT :role_id, p.id FROM permissions p"
                    " WHERE p.code = :code"
                    " AND NOT EXISTS ("
                    "   SELECT 1 FROM role_permissions rp"
                    "   WHERE rp.role_id = :role_id AND rp.permission_id = p.id"
                    " )"
                ),
                {"role_id": role_id, "code": code},
            )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN"
            " (SELECT id FROM permissions WHERE code IN :codes)"
        ).bindparams(sa.bindparam("codes", value=_CODES, expanding=True))
    )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", value=_CODES, expanding=True)
        )
    )

    op.drop_index(op.f("ix_classes_program_id"), table_name="classes")
    op.drop_table("classes")
