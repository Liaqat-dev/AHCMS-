"""rbac tables and seed

Revision ID: a1b2c3d4e5f6
Revises: f25a658c4bd6
Create Date: 2026-07-13
"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f25a658c4bd6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The seed is frozen at this revision on purpose: it must describe the schema
# and catalog as they were *here*, not as `app.core.permissions` /
# `app.db.seed` look today. Importing the live seed made this migration fail
# on a fresh database once `roles.is_system` was added in b2c3d4e5f6a7.
_ROLES: tuple[tuple[str, str], ...] = (
    ("super_admin", "Full access, including role and permission management"),
    ("teacher", "Teaching faculty"),
)

_PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("students:read", "View students"),
    ("students:write", "Create/update students and set their portal passwords"),
    ("faculty:read", "View faculty"),
    ("faculty:write", "Create/update/delete faculty"),
    ("courses:read", "View courses"),
    ("courses:write", "Create/update/delete courses"),
    ("enrollments:read", "View enrollments"),
    ("enrollments:write", "Create/update/delete enrollments"),
    ("users:read", "View staff accounts"),
    ("users:write", "Create staff accounts and assign roles"),
    ("roles:read", "View roles and permissions"),
    ("roles:write", "Create roles and change the permissions they carry"),
)

_GRANTS: dict[str, tuple[str, ...]] = {
    "super_admin": tuple(code for code, _ in _PERMISSIONS),
    "teacher": (
        "students:read",
        "faculty:read",
        "courses:read",
        "enrollments:read",
        "enrollments:write",
    ),
}


def upgrade() -> None:
    op.create_table('roles',
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_roles_name'), 'roles', ['name'], unique=True)

    op.create_table('permissions',
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_permissions_code'), 'permissions', ['code'], unique=True)

    op.create_table('user_roles',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'role_id')
    )

    op.create_table('role_permissions',
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('permission_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )

    # Superseded by the super_admin role.
    op.drop_column('users', 'is_superuser')

    # Seed roles, the permission catalog, and default role -> permission grants.
    _seed(op.get_bind())


def _seed(conn: sa.Connection) -> None:
    roles = sa.table(
        "roles",
        sa.column("id", sa.Uuid),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid),
        sa.column("code", sa.String),
        sa.column("description", sa.String),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Uuid),
        sa.column("permission_id", sa.Uuid),
    )

    role_ids = {name: uuid.uuid4() for name, _ in _ROLES}
    perm_ids = {code: uuid.uuid4() for code, _ in _PERMISSIONS}

    conn.execute(
        roles.insert(),
        [
            {"id": role_ids[name], "name": name, "description": description}
            for name, description in _ROLES
        ],
    )
    conn.execute(
        permissions.insert(),
        [
            {"id": perm_ids[code], "code": code, "description": description}
            for code, description in _PERMISSIONS
        ],
    )
    conn.execute(
        role_permissions.insert(),
        [
            {"role_id": role_ids[role_name], "permission_id": perm_ids[code]}
            for role_name, codes in _GRANTS.items()
            for code in codes
        ],
    )


def downgrade() -> None:
    op.add_column('users', sa.Column('is_superuser', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.drop_table('role_permissions')
    op.drop_table('user_roles')
    op.drop_index(op.f('ix_permissions_code'), table_name='permissions')
    op.drop_table('permissions')
    op.drop_index(op.f('ix_roles_name'), table_name='roles')
    op.drop_table('roles')
