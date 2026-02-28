"""Time helpers.

Keep all timestamps consistent and timezone-aware.
Python 3.13 deprecates naive UTC helpers like datetime.utcnow(); use this module instead.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return the current time as a timezone-aware datetime in UTC (+00:00)."""

    return datetime.now(timezone.utc)
