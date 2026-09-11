"""Academic sessions, generated roll numbers, and full admission details

Three related changes:

* ``academic_sessions`` — the two-year batch a student belongs to. It holds
  only the start year and ``next_roll_seq``, the counter behind that batch's
  roll numbers ("2022-001"), bumped with an atomic UPDATE ... RETURNING.
  ``end_year`` and the "2022-2024" label are derived in the model, not stored.
* ``students`` — ``full_name`` splits into ``first_name``/``last_name``, and
  the record gains admission details: CNIC/B-Form, guardians, contact, address
  and prior (SSC) education. Everything except the name and session is
  nullable: a record is opened at admission and completed over the weeks that
  follow.
* Two new permissions, ``sessions:read`` and ``sessions:write``. Writing is
  administrative and is granted only to ``super_admin`` here; a teacher gets it
  only if a super-admin grants it to their role at runtime.

The permission rows are inserted inline rather than by importing
``app.db.seed``, so re-running this revision years from now reproduces exactly
these grants and not whatever the catalog happens to say by then.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-08
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PERMISSIONS = (
    ("sessions:read", "View academic sessions"),
    ("sessions:write", "Create academic sessions (student batches)"),
)
# role name -> permission codes this revision grants it
_GRANTS = {
    "super_admin": ("sessions:read", "sessions:write"),
    "teacher": ("sessions:read",),
}

_STUDENT_COLUMNS = (
    ("b_form_cnic", sa.String(13)),
    ("date_of_birth", sa.Date()),
    ("father_name", sa.String(150)),
    ("father_cnic", sa.String(13)),
    ("mother_name", sa.String(150)),
    ("cell_no", sa.String(20)),
    ("address", sa.Text()),
    ("last_school_name", sa.String(255)),
    ("ssc_roll_no", sa.String(32)),
    ("ssc_marks_obtained", sa.SmallInteger()),
    ("ssc_marks_total", sa.SmallInteger()),
    ("ssc_year", sa.SmallInteger()),
)

# Split full_name on the first space. A single-word name leaves nothing for the
# surname, so it gets a placeholder rather than blocking the migration — those
# rows need a human to correct them afterwards.
_SPLIT_NAMES = """
    UPDATE students SET
        first_name = COALESCE(NULLIF(split_part(full_name, ' ', 1), ''), '-'),
        last_name  = CASE
            WHEN position(' ' in full_name) > 0
            THEN substring(full_name from position(' ' in full_name) + 1)
            ELSE '-'
        END
"""


def upgrade() -> None:
    bind = op.get_bind()

    # ----- academic_sessions -------------------------------------------------
    op.create_table(
        "academic_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("start_year", sa.SmallInteger(), nullable=False),
        sa.Column("next_roll_seq", sa.Integer(), nullable=False, server_default="1"),
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
        sa.UniqueConstraint("start_year", name="uq_academic_sessions_start_year"),
    )

    # ----- students: names ---------------------------------------------------
    op.add_column("students", sa.Column("first_name", sa.String(100), nullable=True))
    op.add_column("students", sa.Column("last_name", sa.String(100), nullable=True))
    op.execute(_SPLIT_NAMES)
    op.alter_column("students", "first_name", existing_type=sa.String(100), nullable=False)
    op.alter_column("students", "last_name", existing_type=sa.String(100), nullable=False)
    op.drop_column("students", "full_name")

    # ----- students: admission details ---------------------------------------
    for name, column_type in _STUDENT_COLUMNS:
        op.add_column("students", sa.Column(name, column_type, nullable=True))
    op.create_index(
        op.f("ix_students_b_form_cnic"), "students", ["b_form_cnic"], unique=True
    )
    op.create_index(op.f("ix_students_father_cnic"), "students", ["father_cnic"])

    # ----- students: session -------------------------------------------------
    op.add_column("students", sa.Column("session_id", sa.Uuid(), nullable=True))
    # Existing students predate sessions, so park them in one created here
    # rather than failing the NOT NULL. Only runs if there is anything to move.
    orphaned = bind.execute(sa.text("SELECT count(*) FROM students")).scalar() or 0
    if orphaned:
        fallback_id = uuid.uuid4()
        start_year = bind.execute(
            sa.text("SELECT extract(year from now())::int")
        ).scalar()
        bind.execute(
            sa.text(
                "INSERT INTO academic_sessions (id, start_year, next_roll_seq)"
                " VALUES (:id, :start, :seq)"
            ),
            {
                "id": fallback_id,
                "start": start_year,
                # Existing roll numbers were entered by hand and are left as
                # they are; start the counter past them so a generated number
                # cannot collide with one of them.
                "seq": orphaned + 1,
            },
        )
        bind.execute(
            sa.text("UPDATE students SET session_id = :id WHERE session_id IS NULL"),
            {"id": fallback_id},
        )
    op.alter_column("students", "session_id", existing_type=sa.Uuid(), nullable=False)
    op.create_index(op.f("ix_students_session_id"), "students", ["session_id"])
    op.create_foreign_key(
        "fk_students_session_id_academic_sessions",
        "students",
        "academic_sessions",
        ["session_id"],
        ["id"],
        ondelete="RESTRICT",
    )

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
            " (SELECT id FROM permissions WHERE code IN ('sessions:read', 'sessions:write'))"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM permissions WHERE code IN ('sessions:read', 'sessions:write')"
        )
    )

    op.drop_constraint(
        "fk_students_session_id_academic_sessions", "students", type_="foreignkey"
    )
    op.drop_index(op.f("ix_students_session_id"), table_name="students")
    op.drop_column("students", "session_id")

    op.drop_index(op.f("ix_students_father_cnic"), table_name="students")
    op.drop_index(op.f("ix_students_b_form_cnic"), table_name="students")
    for name, _ in reversed(_STUDENT_COLUMNS):
        op.drop_column("students", name)

    op.add_column("students", sa.Column("full_name", sa.String(255), nullable=True))
    op.execute("UPDATE students SET full_name = trim(first_name || ' ' || last_name)")
    op.alter_column("students", "full_name", existing_type=sa.String(255), nullable=False)
    op.drop_column("students", "last_name")
    op.drop_column("students", "first_name")

    op.drop_table("academic_sessions")
