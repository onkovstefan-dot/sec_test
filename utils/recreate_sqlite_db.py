"""Delete and recreate the local SQLite DB.

This is a destructive helper for local development.
It removes `data/sec.db` and recreates all tables from SQLAlchemy models.

Why: SQLite doesn't auto-migrate when models change (e.g. new `units` table,
new `value_names.unit_id`).
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow running as: `python utils/recreate_sqlite_db.py`
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine

from models import Base

# Ensure all model modules are imported so they are registered with Base.metadata
# (Otherwise some tables may not be included in create_all/drop_all)
import models.daily_values  # noqa: F401
import models.dates  # noqa: F401
import models.entities  # noqa: F401
import models.entity_metadata  # noqa: F401
import models.file_processing  # noqa: F401
import models.units  # noqa: F401
import models.value_names  # noqa: F401

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sec.db")


def _confirm_or_exit(db_path: str, assume_yes: bool) -> None:
    if assume_yes:
        return
    resp = input(
        f"This will DROP and RECREATE ALL TABLES in: {db_path}\n"
        "Any data in this database will be lost. Continue? [y/N]: "
    ).strip()
    if resp.lower() not in {"y", "yes"}:
        print("Aborted.")
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Reset the local SQLite database by dropping and recreating all tables."
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Do not prompt for confirmation.",
    )
    args = parser.parse_args(argv)

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    _confirm_or_exit(DB_PATH, args.yes)

    # If a previous process crashed, these can linger and block writes.
    for suffix in ("-wal", "-shm"):
        p = DB_PATH + suffix
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                # Not fatal; SQLite can usually regenerate them.
                pass

    engine = create_engine(f"sqlite:///{DB_PATH}")

    # Drop then recreate all tables (in-place reset)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("Reset DB schema: dropped and recreated all tables from current models.")


if __name__ == "__main__":
    main()
