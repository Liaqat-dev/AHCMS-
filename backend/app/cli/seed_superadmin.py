"""Bootstrap (or repair) the super-admin account from env configuration.

Usage: ``python -m app.cli.seed_superadmin``
Reads ``SUPERADMIN_EMAIL`` / ``SUPERADMIN_PASSWORD`` from settings. Idempotent:
creates the user if missing, re-activates it, and ensures the ``super_admin``
role is attached. Never overwrites an existing password.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.permissions import ROLE_SUPER_ADMIN
from app.core.security import hash_password
from app.db.models import Role, User
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("app.cli.seed_superadmin")


async def seed_superadmin() -> int:
    email = settings.SUPERADMIN_EMAIL
    password = settings.SUPERADMIN_PASSWORD
    if not email or not password:
        logger.info("SUPERADMIN_EMAIL/SUPERADMIN_PASSWORD not set; skipping bootstrap")
        return 0

    async with AsyncSessionLocal() as db:
        role = await db.scalar(select(Role).where(Role.name == ROLE_SUPER_ADMIN))
        if role is None:
            logger.error("Role %r not found — run migrations first", ROLE_SUPER_ADMIN)
            return 1

        user = await db.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            user = User(
                email=email.lower(),
                hashed_password=hash_password(password),
                full_name="Super Admin",
                roles=[role],
            )
            db.add(user)
            logger.info("Created super-admin %s", email)
        else:
            user.is_active = True
            if role.id not in {r.id for r in user.roles}:
                user.roles.append(role)
            logger.info("Ensured super-admin role/active on existing user %s", email)
        await db.commit()
    return 0


if __name__ == "__main__":
    configure_logging()
    sys.exit(asyncio.run(seed_superadmin()))
