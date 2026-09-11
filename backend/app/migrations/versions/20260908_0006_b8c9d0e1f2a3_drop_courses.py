"""Remove the courses placeholder

``subjects`` now does what ``courses`` was a placeholder for -- a taught
subject, shared across classes -- and the real ``enrollments`` table (previous
revision) points at classes and subjects, not courses. Keeping an unused
``courses`` table and its two permissions only invites someone to build against
the wrong one.

Dropped here: the ``courses`` table, and the ``courses:read`` /
``courses:write`` permission rows together with every grant of them. ``faculty``
is untouched -- it is still where a subject's ``teacher_id`` is heading.

This is deliberately a separate revision from the enrollment work: it is a
removal, and separating it keeps the enrollment revision reversible on its own.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-08
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CODES = ("courses:read", "courses:write")
# What the initial revision seeded, restored verbatim on downgrade.
_PERMISSIONS = (
    ("courses:read", "View courses"),
    ("courses:write", "Create/update/delete courses"),
)
_GRANTS = {
    "super_admin": ("courses:read", "courses:write"),
    "teacher": ("courses:read",),
}


def upgrade() -> None:
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

    # The placeholder enrollments table referenced this and was dropped in the
    # previous revision, so nothing points at it any more.
    op.drop_index(op.f("ix_courses_code"), table_name="courses")
    op.drop_table("courses")


def downgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
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
        sa.UniqueConstraint("code", name="uq_courses_code"),
    )
    op.create_index(op.f("ix_courses_code"), "courses", ["code"])

    for code, description in _PERMISSIONS:
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
                    " SELECT :role_id, p.id FROM permissions p WHERE p.code = :code"
                ),
                {"role_id": role_id, "code": code},
            )
