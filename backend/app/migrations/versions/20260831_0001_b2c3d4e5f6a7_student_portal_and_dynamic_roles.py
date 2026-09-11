"""Student portal credentials, dynamic roles, and two seed roles

Three related changes:

* ``students`` gains portal credentials, so a student can sign in with a roll
  number and password. A student is not a ``User`` and holds no roles.
* ``refresh_sessions`` becomes polymorphic: a session belongs to a staff user
  OR a student, enforced by a check constraint.
* ``roles`` gains ``is_system``. The seed roles drop from four to two
  (``super_admin``, ``teacher``); ``student`` and ``admin`` are removed, since
  students are no longer a role and roles are now created at runtime.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-31
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Roles that are no longer seeded. Students authenticate against their own
# table, and `admin` collapses into runtime-created roles.
_REMOVED_ROLES = ("student", "admin")
_SYSTEM_ROLES = ("super_admin",)


def upgrade() -> None:
    # ----- students: portal credentials -------------------------------------
    op.add_column("students", sa.Column("hashed_password", sa.String(255), nullable=True))
    op.add_column(
        "students",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    # The default exists only to backfill existing rows; new rows get it from
    # the model, so drop it and keep the column's intent in one place.
    op.alter_column("students", "is_active", server_default=None)

    # ----- roles: system flag ------------------------------------------------
    op.add_column(
        "roles",
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("roles", "is_system", server_default=None)

    roles = sa.table("roles", sa.column("name", sa.String), sa.column("is_system", sa.Boolean))
    op.execute(
        roles.update().where(roles.c.name.in_(_SYSTEM_ROLES)).values(is_system=True)
    )

    # ----- refresh_sessions: staff user OR student ---------------------------
    op.add_column("refresh_sessions", sa.Column("student_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_refresh_sessions_student_id"), "refresh_sessions", ["student_id"]
    )
    op.create_foreign_key(
        "fk_refresh_sessions_student_id_students",
        "refresh_sessions",
        "students",
        ["student_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("refresh_sessions", "user_id", existing_type=sa.Uuid(), nullable=True)
    op.create_check_constraint(
        "ck_refresh_sessions_one_subject",
        "refresh_sessions",
        "(user_id IS NOT NULL AND student_id IS NULL)"
        " OR (user_id IS NULL AND student_id IS NOT NULL)",
    )

    # ----- drop the roles that no longer exist -------------------------------
    # Delete grants and assignments first so the FKs stay satisfied on any
    # database whose constraints are not ON DELETE CASCADE.
    op.execute(
        "DELETE FROM role_permissions WHERE role_id IN "
        f"(SELECT id FROM roles WHERE name IN {_in_list(_REMOVED_ROLES)})"
    )
    op.execute(
        "DELETE FROM user_roles WHERE role_id IN "
        f"(SELECT id FROM roles WHERE name IN {_in_list(_REMOVED_ROLES)})"
    )
    op.execute(f"DELETE FROM roles WHERE name IN {_in_list(_REMOVED_ROLES)}")


def downgrade() -> None:
    op.drop_constraint(
        "ck_refresh_sessions_one_subject", "refresh_sessions", type_="check"
    )
    # Sessions belonging to students have no place in the old schema.
    op.execute("DELETE FROM refresh_sessions WHERE student_id IS NOT NULL")
    op.alter_column("refresh_sessions", "user_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_constraint(
        "fk_refresh_sessions_student_id_students", "refresh_sessions", type_="foreignkey"
    )
    op.drop_index(op.f("ix_refresh_sessions_student_id"), table_name="refresh_sessions")
    op.drop_column("refresh_sessions", "student_id")

    op.drop_column("roles", "is_system")

    op.drop_column("students", "is_active")
    op.drop_column("students", "hashed_password")
    # The `student`/`admin` roles are not recreated: re-running the previous
    # revision's seed is the supported way to restore them.


def _in_list(values: tuple[str, ...]) -> str:
    """Render a tuple as a SQL IN-list literal, e.g. ``('student', 'admin')``."""
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"
