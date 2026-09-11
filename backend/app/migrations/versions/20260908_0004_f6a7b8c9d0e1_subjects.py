"""Subjects, the class_subjects link, and two permissions

A subject is a taught subject with a unique ``name`` and ``code``, plus a seat
budget: ``student_limit`` (default 30) and ``student_count`` (starts at 0).
Both are guarded by check constraints -- non-negative, a positive limit, and
the count never above the limit -- which back up the checks the service does
first so a violation is a 400, not a 500.

``class_subjects`` is the many-to-many between classes and subjects: one class
runs several subjects and one subject is taught to several classes. It carries
no facts of its own, so both foreign keys are ON DELETE CASCADE.

There is no ``teacher_id`` column: which table a teacher lives in (a staff
``User`` with the ``teacher`` role, or the still-unimplemented ``faculty``) is
a decision deferred to when faculty is built out.

``subjects:read`` is granted to ``teacher`` as well as ``super_admin``;
``subjects:write`` goes only to ``super_admin``. As in the previous revisions
the permission rows are inserted inline rather than by importing
``app.db.seed``, so re-running this revision years from now reproduces exactly
these grants.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-08
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_STUDENT_LIMIT = "30"

_NEW_PERMISSIONS = (
    ("subjects:read", "View subjects"),
    ("subjects:write", "Create/update/delete subjects and the classes they run in"),
)
# role name -> permission codes this revision grants it
_GRANTS = {
    "super_admin": ("subjects:read", "subjects:write"),
    "teacher": ("subjects:read",),
}
_CODES = tuple(code for code, _ in _NEW_PERMISSIONS)


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "subjects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column(
            "student_limit",
            sa.Integer(),
            nullable=False,
            server_default=_DEFAULT_STUDENT_LIMIT,
        ),
        sa.Column("student_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.CheckConstraint("student_count >= 0", name="ck_subjects_student_count_positive"),
        sa.CheckConstraint("student_limit > 0", name="ck_subjects_student_limit_positive"),
        sa.CheckConstraint("student_count <= student_limit", name="ck_subjects_count_within_limit"),
        sa.UniqueConstraint("name", name="uq_subjects_name"),
        sa.UniqueConstraint("code", name="uq_subjects_code"),
    )
    op.create_index(op.f("ix_subjects_code"), "subjects", ["code"])

    op.create_table(
        "class_subjects",
        sa.Column("class_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["classes.id"],
            name="fk_class_subjects_class_id_classes",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name="fk_class_subjects_subject_id_subjects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("class_id", "subject_id"),
    )
    # The primary key already covers class_id-first lookups; this one serves
    # "which classes run this subject".
    op.create_index(op.f("ix_class_subjects_subject_id"), "class_subjects", ["subject_id"])

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

    op.drop_index(op.f("ix_class_subjects_subject_id"), table_name="class_subjects")
    op.drop_table("class_subjects")
    op.drop_index(op.f("ix_subjects_code"), table_name="subjects")
    op.drop_table("subjects")
