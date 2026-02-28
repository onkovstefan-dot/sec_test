"""Time helpers.

Keep all timestamps consistent and timezone-aware.
Python 3.13 deprecates naive UTC helpers like datetime.utcnow(); use this module instead.
"""

from __future__ import annotations

from datetime import datetime, timezone, date


def utcnow() -> datetime:
    """Return the current time as a timezone-aware datetime in UTC (+00:00)."""

    return datetime.now(timezone.utc)


def utcnow_sa_default() -> datetime:
    """SQLAlchemy-friendly default callable for UTC timestamps.

    Prefer this over passing `utcnow` directly if you want the intent to be explicit.
    """

    return utcnow()


def ensure_utc(dt: datetime) -> datetime:
    """Return a timezone-aware UTC datetime.

    - If `dt` is naive, it is treated as UTC.
    - If `dt` is timezone-aware, it is converted to UTC.
    """

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_ymd_date(date_str: str) -> date:
    """Parse a YYYY-MM-DD string into a `datetime.date`.

    Raises:
        ValueError: if `date_str` is not a valid YYYY-MM-DD date.
    """

    # Use `date.fromisoformat` (fast, strict) rather than `datetime.strptime(...).date()`.
    return date.fromisoformat(date_str)
