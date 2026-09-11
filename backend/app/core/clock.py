"""The college's calendar day.

Attendance is dated by day, so "today" has to mean today *at the college*. The
server runs UTC on Render, where 1am in Karachi is still the previous date —
using the server's own date would silently file an early-morning register under
yesterday, and reject a legitimate one as "in the future" late at night.

One place computes it, from ``COLLEGE_TIMEZONE``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.core.config import settings


@lru_cache(maxsize=1)
def college_tz() -> ZoneInfo:
    """The configured zone. Cached — building it reads the tz database."""
    return ZoneInfo(settings.COLLEGE_TIMEZONE)


def college_now() -> datetime:
    return datetime.now(college_tz())


def college_today() -> date:
    return college_now().date()


def to_college_date(moment: datetime) -> date:
    """Which college day an instant falls on.

    A naive value is read as UTC: that is what the database hands back on
    SQLite, and every timestamp the app writes is UTC underneath.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(college_tz()).date()


def end_of_day(on: date) -> datetime:
    """The instant the college's day ends — midnight at the start of the next.

    Used instead of casting a stored timestamp to a date in SQL. Postgres would
    cast using the *server's* zone (UTC on Render), which puts an evening
    enrolment on the wrong day, and SQLite has no date type to cast to at all.
    Comparing instants avoids both.
    """
    return datetime.combine(on + timedelta(days=1), time.min, tzinfo=college_tz())
