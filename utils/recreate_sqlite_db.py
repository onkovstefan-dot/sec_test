"""Delete and recreate the local SQLite DB.

This is a destructive helper for local development.
It removes `data/sec.db` and recreates all tables from SQLAlchemy models.

Why: SQLite doesn't auto-migrate when models change (e.g. new `units` table,
new `value_names.unit_id`, new metadata fields).

Usage:
    python utils/recreate_sqlite_db.py          # with confirmation prompt
    python utils/recreate_sqlite_db.py --yes    # skip confirmation
    python utils/recreate_sqlite_db.py --backup # create backup before reset
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime

# Allow running as: `python utils/recreate_sqlite_db.py`
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, inspect

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
    """Prompt user for confirmation before proceeding with destructive operation."""
    if assume_yes:
        return

    # Check if database exists and show size
    if os.path.exists(db_path):
        size_mb = os.path.getsize(db_path) / (1024 * 1024)
        print(f"\n⚠️  WARNING: Database exists ({size_mb:.2f} MB)")

    resp = input(
        f"\nThis will DROP and RECREATE ALL TABLES in:\n  {db_path}\n\n"
        "⚠️  ALL DATA WILL BE LOST!\n\n"
        "Continue? [y/N]: "
    ).strip()
    if resp.lower() not in {"y", "yes"}:
        print("Aborted.")
        raise SystemExit(1)


def _create_backup(db_path: str) -> str | None:
    """Create a timestamped backup of the database."""
    if not os.path.exists(db_path):
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"

    try:
        shutil.copy2(db_path, backup_path)
        size_mb = os.path.getsize(backup_path) / (1024 * 1024)
        print(f"✓ Backup created: {backup_path} ({size_mb:.2f} MB)")
        return backup_path
    except Exception as e:
        print(f"⚠️  Failed to create backup: {e}")
        return None


def _show_existing_tables(db_path: str) -> None:
    """Show tables in the existing database."""
    if not os.path.exists(db_path):
        print("Database does not exist yet.")
        return

    try:
        engine = create_engine(f"sqlite:///{db_path}")
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if tables:
            print(f"\nExisting tables ({len(tables)}):")
            for table in sorted(tables):
                print(f"  - {table}")
        else:
            print("\nNo tables found in database.")

        engine.dispose()
    except Exception as e:
        print(f"Could not inspect database: {e}")


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
    parser.add_argument(
        "--backup",
        "-b",
        action="store_true",
        help="Create a timestamped backup before resetting.",
    )
    args = parser.parse_args(argv)

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # Show existing tables before reset
    _show_existing_tables(DB_PATH)

    _confirm_or_exit(DB_PATH, args.yes)

    # Create backup if requested
    if args.backup:
        _create_backup(DB_PATH)

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

    # Try to drop all tables gracefully
    print("\n🔄 Dropping all tables...")
    try:
        Base.metadata.drop_all(engine)
    except Exception as e:
        print(f"⚠️  Could not drop tables gracefully: {e}")
        print("🗑️  Deleting database file and recreating from scratch...")
        engine.dispose()

        # Remove the database file entirely
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

        # Recreate engine with fresh database
        engine = create_engine(f"sqlite:///{DB_PATH}")

    print("🔨 Recreating all tables from models...")
    Base.metadata.create_all(engine)

    # Show new tables
    print("\n✓ Database reset complete!")
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\nRecreated tables ({len(tables)}):")
    for table in sorted(tables):
        print(f"  - {table}")

    engine.dispose()
    print(f"\nDatabase location: {DB_PATH}")


if __name__ == "__main__":
    main()
