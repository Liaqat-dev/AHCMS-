"""Attendance registers and their two permissions

* ``attendance_sheets`` -- one register per class per calendar day, with
  ``UNIQUE(class_id, date)`` holding that rule. A day with no sheet is a day the
  class did not meet, so no calendar of holidays is needed. The class FK is
  RESTRICT: a term of registers should not vanish with one class deletion.
* ``attendance_records`` -- one mark per student per sheet. Rows exist only once
  somebody marks: a student with no record is *unmarked*, which is neither
  present nor absent. ``status`` is a short string with a CHECK rather than a
  native ENUM, so adding a value later is a constraint change instead of a
  locking type alteration.

Records key on ``student_id``, not on the enrollment -- the opposite of
``subject_enrollments``. A subject choice only means anything inside the
enrollment that owns it; an attendance mark is a fact about a day that already
happened, and must survive the student moving class.

``attendance:read`` and ``attendance:write`` both go to ``teacher`` as well as
``super_admin``: taking the register is a teacher's daily job, and any staff
member may mark any class. As in the previous revisions the permission rows are
inserted inline rather than by importing ``app.db.seed``.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-08
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUSES = ("present", "absent", "leave")
_STATUS_CHECK = "status IN ('{}')".format("', '".join(_STATUSES))

_NEW_PERMISSIONS = (
    ("attendance:read", "View attendance registers"),
    ("attendance:write", "Open attendance registers and mark students"),
)
# role name -> permission codes this revision grants it
_GRANTS = {
    "super_admin": ("attendance:read", "attendance:write"),
    # Both, not just read: marking is the teacher's daily job.
    "teacher": ("attendance:read", "attendance:write"),
}
_CODES = tuple(code for code, _ in _NEW_PERMISSIONS)


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "attendance_sheets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("class_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("marked_by_id", sa.Uuid(), nullable=True),
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
            name="fk_attendance_sheets_class_id_classes",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["marked_by_id"],
            ["users.id"],
            name="fk_attendance_sheets_marked_by_id_users",
            ondelete="SET NULL",
        ),
        # The "one register per class per day" rule.
        sa.UniqueConstraint("class_id", "date", name="uq_attendance_sheets_class_date"),
    )
    op.create_index(op.f("ix_attendance_sheets_class_id"), "attendance_sheets", ["class_id"])
    op.create_index(op.f("ix_attendance_sheets_date"), "attendance_sheets", ["date"])

    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sheet_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("marked_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "marked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["sheet_id"],
            ["attendance_sheets.id"],
            name="fk_attendance_records_sheet_id_attendance_sheets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="fk_attendance_records_student_id_students",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["marked_by_id"],
            ["users.id"],
            name="fk_attendance_records_marked_by_id_users",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("sheet_id", "student_id", name="uq_attendance_records_pair"),
        sa.CheckConstraint(_STATUS_CHECK, name="ck_attendance_records_status"),
    )
    op.create_index(op.f("ix_attendance_records_sheet_id"), "attendance_records", ["sheet_id"])
    op.create_index(op.f("ix_attendance_records_student_id"), "attendance_records", ["student_id"])

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

    op.drop_index(op.f("ix_attendance_records_student_id"), table_name="attendance_records")
    op.drop_index(op.f("ix_attendance_records_sheet_id"), table_name="attendance_records")
    op.drop_table("attendance_records")

    op.drop_index(op.f("ix_attendance_sheets_date"), table_name="attendance_sheets")
    op.drop_index(op.f("ix_attendance_sheets_class_id"), table_name="attendance_sheets")
    op.drop_table("attendance_sheets")
