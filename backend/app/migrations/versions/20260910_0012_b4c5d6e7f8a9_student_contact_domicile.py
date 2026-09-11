"""Student guardian cell number, province and domicile district.

Three columns the admission form was collecting nowhere. All nullable, because
every optional field on a student record is: the file is opened with a name and
an intake, and the rest arrives over the following weeks.

Deliberately **not** added to ``REQUIRED_FOR_COMPLETION``. That tuple drives the
"N outstanding" badge on every student, and widening it here would mark every
record already on file as less complete than it was yesterday without anybody
having changed one. Adding them there is a separate decision.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-09-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("students", sa.Column("guardian_cell_no", sa.String(length=20), nullable=True))
    op.add_column("students", sa.Column("province", sa.String(length=64), nullable=True))
    op.add_column("students", sa.Column("domicile_district", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("students", "domicile_district")
    op.drop_column("students", "province")
    op.drop_column("students", "guardian_cell_no")
