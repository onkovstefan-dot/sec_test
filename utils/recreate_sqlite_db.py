"""Delete and recreate the local SQLite DB.

This is a destructive helper for local development.
It removes `data/sec.db` and recreates all tables from SQLAlchemy models.

Why: SQLite doesn't auto-migrate when models change (e.g. new `units` table,
new `value_names.unit_id`).
"""

from __future__ import annotations

import os
import sys

# Allow running as: `python utils/recreate_sqlite_db.py`
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine

from models import Base

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sec.db")


def main() -> None:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Deleted existing DB: {DB_PATH}")
    else:
        print(f"No existing DB found at: {DB_PATH}")

    engine = create_engine(f"sqlite:///{DB_PATH}")
    Base.metadata.create_all(engine)
    print("Recreated DB schema from current models.")


if __name__ == "__main__":
    main()
