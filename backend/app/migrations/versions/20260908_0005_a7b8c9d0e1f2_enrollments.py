"""Class enrollment and optional subject choices

Replaces the placeholder ``enrollments`` table (student x course, never given
endpoints) with the real thing:

* ``enrollments`` -- one row per student, ``UNIQUE(student_id)``. That single
  constraint is the whole "a student enrolls in exactly one class" rule, held
  by the database rather than by convention. A student who changes class
  updates the row; no history is kept.
* ``subject_enrollments`` -- the optional subjects, keyed to the **enrollment**
  rather than the student. A pick therefore cannot exist without a class
  enrollment, and dropping the enrollment drops the picks (CASCADE). The
  subject side is RESTRICT, so deleting a subject students have taken up is a
  409 from the service rather than a silent loss of their choices.

The rule the schema cannot state -- that a picked subject must be one the
enrolled class actually runs -- is enforced in ``app.services.enrollments``.

No permission rows: ``enrollments:read`` and ``enrollments:write`` were seeded
in the initial RBAC revision and are already granted to both seed roles. No
backfill: nothing has ever written to ``classes``, so no student has one.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-08
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ----- out with the placeholder ------------------------------------------
    # student x course, no endpoints, no rows. Its name is the one we want.
    op.drop_table("enrollments")

    # ----- enrollments: one class per student --------------------------------
    op.create_table(
        "enrollments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("class_id", sa.Uuid(), nullable=False),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
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
            ["student_id"],
            ["students.id"],
            name="fk_enrollments_student_id_students",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["classes.id"],
            name="fk_enrollments_class_id_classes",
            ondelete="RESTRICT",
        ),
        # The "only one class" rule.
        sa.UniqueConstraint("student_id", name="uq_enrollments_student"),
    )
    op.create_index(op.f("ix_enrollments_class_id"), "enrollments", ["class_id"])

    # ----- subject_enrollments: the optional picks ---------------------------
    op.create_table(
        "subject_enrollments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["enrollments.id"],
            name="fk_subject_enrollments_enrollment_id_enrollments",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name="fk_subject_enrollments_subject_id_subjects",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "enrollment_id", "subject_id", name="uq_subject_enrollments_pair"
        ),
    )
    op.create_index(
        op.f("ix_subject_enrollments_enrollment_id"),
        "subject_enrollments",
        ["enrollment_id"],
    )
    op.create_index(
        op.f("ix_subject_enrollments_subject_id"), "subject_enrollments", ["subject_id"]
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_subject_enrollments_subject_id"), table_name="subject_enrollments"
    )
    op.drop_index(
        op.f("ix_subject_enrollments_enrollment_id"), table_name="subject_enrollments"
    )
    op.drop_table("subject_enrollments")

    op.drop_index(op.f("ix_enrollments_class_id"), table_name="enrollments")
    op.drop_table("enrollments")

    # Restore the placeholder exactly as the initial schema had it.
    op.create_table(
        "enrollments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
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
            ["student_id"],
            ["students.id"],
            name="fk_enrollments_student_id_students",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name="fk_enrollments_course_id_courses",
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_enrollments_student_id"), "enrollments", ["student_id"])
    op.create_index(op.f("ix_enrollments_course_id"), "enrollments", ["course_id"])
