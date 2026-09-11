"""Name the teacher of a subject

Closes the ``teacher_id`` question left open when subjects were built: the
column points at ``faculty``, not at ``users``. Teaching is a fact about a
person on the college's books, and plenty of them never sign in to anything;
a staff account that exists only to administer the system is not a teacher.

Nullable, because a subject is usually created before the timetable is settled.
ON DELETE RESTRICT rather than SET NULL: a subject quietly losing its teacher
because somebody tidied a personnel file is the kind of change nobody notices
until a timetable is printed. ``services.faculty.delete_member`` refuses first,
naming the subjects, so the constraint is a backstop rather than the usual path.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-08
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("subjects", sa.Column("teacher_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_subjects_teacher_id"), "subjects", ["teacher_id"])
    op.create_foreign_key(
        "fk_subjects_teacher_id_faculty",
        "subjects",
        "faculty",
        ["teacher_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_subjects_teacher_id_faculty", "subjects", type_="foreignkey")
    op.drop_index(op.f("ix_subjects_teacher_id"), table_name="subjects")
    op.drop_column("subjects", "teacher_id")
