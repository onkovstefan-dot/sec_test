from __future__ import annotations


def parse_primitive(text: str | None):
    """Parse a primitive value that was stored as TEXT.

    Heuristics:
    - None/"" -> None
    - booleans: true/false (case-insensitive)
    - ints
    - floats
    - otherwise return original string

    Keep this deliberately small and reusable.
    """

    if text is None:
        return None

    s = str(text).strip()
    if s == "":
        return None

    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False

    # int first (so "1" becomes int not float)
    try:
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            return int(s)
    except Exception:
        pass

    try:
        return float(s)
    except Exception:
        return s
