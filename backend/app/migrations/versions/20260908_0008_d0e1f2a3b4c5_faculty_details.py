"""Full faculty personnel record

``faculty`` existed as a three-column placeholder (employee number, full name,
email) with no endpoints. This gives it the shape a personnel file actually
has, mirroring what ``students`` already does:

* ``full_name`` splits into ``first_name`` / ``last_name``, so faculty sort and
  search the way students do;
* designation, qualification, CNIC, cell number, address and joining date;
* ``is_active``, because someone who leaves should stay nameable on the records
  they are already on rather than being deleted.

Only the employee number and a name are required; the rest of the file is
completed over time, and ``missing_fields`` reports what is outstanding.

No permission rows: ``faculty:read`` and ``faculty:write`` were seeded in the
initial RBAC revision and are already granted.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-08
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_COLUMNS = (
    ("designation", sa.String(64)),
    ("qualification", sa.String(150)),
    ("cnic", sa.String(13)),
    ("cell_no", sa.String(20)),
    ("address", sa.Text()),
    ("joined_on", sa.Date()),
)

# Split full_name on the first space, exactly as the student revision did. A
# single-word name leaves nothing for the surname, so it gets a placeholder
# rather than blocking the migration.
_SPLIT_NAMES = """
    UPDATE faculty SET
        first_name = COALESCE(NULLIF(split_part(full_name, ' ', 1), ''), '-'),
        last_name  = CASE
            WHEN position(' ' in full_name) > 0
            THEN substring(full_name from position(' ' in full_name) + 1)
            ELSE '-'
        END
"""


def upgrade() -> None:
    op.add_column("faculty", sa.Column("first_name", sa.String(100), nullable=True))
    op.add_column("faculty", sa.Column("last_name", sa.String(100), nullable=True))
    op.execute(_SPLIT_NAMES)
    op.alter_column("faculty", "first_name", existing_type=sa.String(100), nullable=False)
    op.alter_column("faculty", "last_name", existing_type=sa.String(100), nullable=False)
    op.drop_column("faculty", "full_name")

    for name, column_type in _NEW_COLUMNS:
        op.add_column("faculty", sa.Column(name, column_type, nullable=True))
    op.create_index(op.f("ix_faculty_cnic"), "faculty", ["cnic"], unique=True)

    op.add_column(
        "faculty",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    # The default exists only to backfill existing rows; new rows get it from
    # the model, so drop it and keep the column's intent in one place.
    op.alter_column("faculty", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("faculty", "is_active")
    op.drop_index(op.f("ix_faculty_cnic"), table_name="faculty")
    for name, _ in reversed(_NEW_COLUMNS):
        op.drop_column("faculty", name)

    op.add_column("faculty", sa.Column("full_name", sa.String(255), nullable=True))
    op.execute("UPDATE faculty SET full_name = trim(first_name || ' ' || last_name)")
    op.alter_column("faculty", "full_name", existing_type=sa.String(255), nullable=False)
    op.drop_column("faculty", "last_name")
    op.drop_column("faculty", "first_name")
