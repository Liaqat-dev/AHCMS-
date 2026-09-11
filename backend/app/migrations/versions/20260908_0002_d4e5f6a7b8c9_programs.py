"""Programs table and its two permissions

A program is a course of study a student is admitted to: a unique ``name``
("Engineering") and a unique three-letter ``code`` ("ENG") short enough to sit
in a timetable cell or a report column. ``created_by_id`` is an audit trail and
goes NULL if the staff account is removed, so deleting a user never blocks on
a program they happened to create.

``programs:read`` is granted to ``teacher`` as well as ``super_admin`` -- naming
a program comes up wherever students are listed -- while ``programs:write``
goes only to ``super_admin``. As in the previous revision the permission rows
are inserted inline rather than by importing ``app.db.seed``, so re-running
this revision years from now reproduces exactly these grants.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-08
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PERMISSIONS = (
    ("programs:read", "View programs"),
    ("programs:write", "Create/update/delete programs"),
)
# role name -> permission codes this revision grants it
_GRANTS = {
    "super_admin": ("programs:read", "programs:write"),
    "teacher": ("programs:read",),
}
_CODES = tuple(code for code, _ in _NEW_PERMISSIONS)


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "programs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code", sa.String(3), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
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
            ["created_by_id"],
            ["users.id"],
            name="fk_programs_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("name", name="uq_programs_name"),
        sa.UniqueConstraint("code", name="uq_programs_code"),
    )
    op.create_index(op.f("ix_programs_code"), "programs", ["code"])
    op.create_index(op.f("ix_programs_created_by_id"), "programs", ["created_by_id"])

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

    op.drop_index(op.f("ix_programs_created_by_id"), table_name="programs")
    op.drop_index(op.f("ix_programs_code"), table_name="programs")
    op.drop_table("programs")
