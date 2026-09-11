"""Recompute ``subjects.student_count`` from the enrollment rows.

Usage: ``python -m app.cli.reconcile_counts``

``student_count`` is a cache maintained by ``app.services.capacity``. It should
never drift — every write goes through one conditional UPDATE inside the same
transaction as the row it counts — but a restore from a partial backup, or a
hand-edited row, can leave it wrong, and a wrong count silently under- or
over-books a subject. This recomputes every one of them from
``subject_enrollments`` and reports what it changed.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid

from sqlalchemy import func, select, update

from app.core.logging import configure_logging
from app.db.models import Subject, SubjectEnrollment
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("app.cli.reconcile_counts")


async def reconcile_counts() -> int:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(SubjectEnrollment.subject_id, func.count()).group_by(
                    SubjectEnrollment.subject_id
                )
            )
        ).all()
        actual: dict[uuid.UUID, int] = dict(rows)  # type: ignore[arg-type]

        drifted = 0
        for subject_id, name, cached in (
            await db.execute(select(Subject.id, Subject.name, Subject.student_count))
        ).all():
            real = actual.get(subject_id, 0)
            if real == cached:
                continue
            drifted += 1
            logger.warning("%s: student_count %d -> %d", name, cached, real)
            await db.execute(
                update(Subject).where(Subject.id == subject_id).values(student_count=real)
            )

        await db.commit()
        logger.info("Reconciled %d subject(s)", drifted)
    return 0


if __name__ == "__main__":
    configure_logging()
    sys.exit(asyncio.run(reconcile_counts()))
