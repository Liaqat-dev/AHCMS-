"""Exams, the papers they consist of, the marks, and the faculty-to-login link

Four changes, all in service of one requirement: a teacher enters marks for the
subjects they teach.

* ``faculty.user_id`` -- nullable and unique. Until now nothing joined the
  signed-in ``User`` to the ``Faculty`` row a subject names as its teacher, so
  "only that teacher may mark this paper" was unenforceable. Most faculty never
  sign in, hence nullable; no login belongs to two people, hence unique.
* ``exams`` -- a paper sat by a class on a date, over one subject or all of
  them. The date may be in the **future**, unlike an attendance register:
  announcing an exam before it happens is the point.
* ``exam_subjects`` -- the subjects an exam actually covered, written down at
  creation. A class's subject list changes; what an exam consisted of does not.
  Each carries its own total.
* ``exam_marks`` -- one student's result in one paper. A row exists only once
  somebody records something, so "not entered" and "zero" stay different. A
  check constraint keeps "absent" and "scored" mutually exclusive.

Seven permissions: exams read/create/update/delete and marks
read/update/update_any. ``teacher`` gets read, create and ``marks:update`` --
which is scoped to their own subjects, so it is safe to ship.
``marks:update_any`` is the office's override and goes to ``super_admin`` only.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-09-08
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCOPE_CHECK = "scope IN ('subject', 'class')"

_NEW_PERMISSIONS = (
    ("exams:read", "View exams"),
    ("exams:create", "Schedule exams"),
    ("exams:update", "Edit exams"),
    ("exams:delete", "Delete exams"),
    ("marks:read", "View exam marks"),
    ("marks:update", "Enter marks for subjects you teach"),
    ("marks:update_any", "Enter marks for any subject"),
)
_GRANTS = {
    "super_admin": tuple(code for code, _ in _NEW_PERMISSIONS),
    # Setting a paper and marking one's own are teaching work. The override is
    # deliberately not here.
    "teacher": ("exams:read", "exams:create", "marks:read", "marks:update"),
}
_CODES = tuple(code for code, _ in _NEW_PERMISSIONS)


def upgrade() -> None:
    bind = op.get_bind()

    # ----- faculty <-> login -------------------------------------------------
    op.add_column("faculty", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_faculty_user_id"), "faculty", ["user_id"], unique=True)
    op.create_foreign_key(
        "fk_faculty_user_id_users",
        "faculty",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ----- exams -------------------------------------------------------------
    op.create_table(
        "exams",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("class_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
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
            ["class_id"],
            ["classes.id"],
            name="fk_exams_class_id_classes",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_exams_created_by_id_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(_SCOPE_CHECK, name="ck_exams_scope"),
    )
    op.create_index(op.f("ix_exams_class_id"), "exams", ["class_id"])
    op.create_index(op.f("ix_exams_date"), "exams", ["date"])

    # ----- exam_subjects -----------------------------------------------------
    op.create_table(
        "exam_subjects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("exam_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("total_marks", sa.Integer(), nullable=False, server_default="100"),
        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            name="fk_exam_subjects_exam_id_exams",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name="fk_exam_subjects_subject_id_subjects",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("exam_id", "subject_id", name="uq_exam_subjects_pair"),
        sa.CheckConstraint("total_marks > 0", name="ck_exam_subjects_total_positive"),
    )
    op.create_index(op.f("ix_exam_subjects_exam_id"), "exam_subjects", ["exam_id"])
    op.create_index(op.f("ix_exam_subjects_subject_id"), "exam_subjects", ["subject_id"])

    # ----- exam_marks --------------------------------------------------------
    op.create_table(
        "exam_marks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("exam_subject_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("obtained", sa.Integer(), nullable=True),
        sa.Column("is_absent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("marked_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "marked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["exam_subject_id"],
            ["exam_subjects.id"],
            name="fk_exam_marks_exam_subject_id_exam_subjects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="fk_exam_marks_student_id_students",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["marked_by_id"],
            ["users.id"],
            name="fk_exam_marks_marked_by_id_users",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("exam_subject_id", "student_id", name="uq_exam_marks_pair"),
        sa.CheckConstraint("obtained IS NULL OR obtained >= 0", name="ck_exam_marks_positive"),
        sa.CheckConstraint(
            "NOT (is_absent AND obtained IS NOT NULL)",
            name="ck_exam_marks_absent_or_score",
        ),
    )
    op.create_index(op.f("ix_exam_marks_exam_subject_id"), "exam_marks", ["exam_subject_id"])
    op.create_index(op.f("ix_exam_marks_student_id"), "exam_marks", ["student_id"])
    op.alter_column("exam_marks", "is_absent", server_default=None)

    # ----- permissions -------------------------------------------------------
    for code, description in _NEW_PERMISSIONS:
        bind.execute(
            sa.text(
                "INSERT INTO permissions (id, code, description)"
                " VALUES (:id, :code, :description) ON CONFLICT (code) DO NOTHING"
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

    op.drop_table("exam_marks")
    op.drop_table("exam_subjects")
    op.drop_index(op.f("ix_exams_date"), table_name="exams")
    op.drop_index(op.f("ix_exams_class_id"), table_name="exams")
    op.drop_table("exams")

    op.drop_constraint("fk_faculty_user_id_users", "faculty", type_="foreignkey")
    op.drop_index(op.f("ix_faculty_user_id"), table_name="faculty")
    op.drop_column("faculty", "user_id")
