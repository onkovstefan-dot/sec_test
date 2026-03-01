"""Delete the local SQLite DB.

This is a destructive helper for local development.

Behavior:
- Optionally create a timestamped backup
- Delete `data/sec.db` (and any `-wal`/`-shm` files)
- Exit

The Flask app recreates tables from SQLAlchemy models on startup.

Usage:
    python utils/recreate_sqlite_db.py          # with confirmation prompt
    python utils/recreate_sqlite_db.py --yes   # skip confirmation
    python utils/recreate_sqlite_db.py --backup
"""

from __future__ import annotations

import argparse
import os
import shutil
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sec.db")


def _confirm_or_exit(db_path: str, assume_yes: bool) -> None:
    """Prompt user for confirmation before proceeding with destructive operation."""
    if assume_yes:
        return

    if os.path.exists(db_path):
        size_mb = os.path.getsize(db_path) / (1024 * 1024)
        print(f"\nWARNING: Database exists ({size_mb:.2f} MB)")

    resp = input(
        f"\nThis will DELETE the SQLite database file (and ALL DATA) at:\n  {db_path}\n\n"
        "ALL DATA WILL BE LOST!\n\n"
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
        print(f"Backup created: {backup_path} ({size_mb:.2f} MB)")
        return backup_path
    except Exception as e:
        print(f"Failed to create backup: {e}")
        return None


def _delete_sqlite_files(db_path: str) -> None:
    """Delete the main sqlite file and associated WAL/SHM files if present."""
    deleted_any = False
    for suffix in ("", "-wal", "-shm"):
        p = db_path + suffix
        if os.path.exists(p):
            try:
                os.remove(p)
                print(f"Deleted: {p}")
                deleted_any = True
            except OSError as e:
                print(f"Could not delete {p}: {e}")

    if not deleted_any:
        print("Nothing to delete (DB file not found).")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Delete the local SQLite database file. "
            "Start the app afterwards to recreate tables from models."
        )
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
        help="Create a timestamped backup before deleting.",
    )
    args = parser.parse_args(argv)

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    _confirm_or_exit(DB_PATH, args.yes)

    if args.backup:
        _create_backup(DB_PATH)

    _delete_sqlite_files(DB_PATH)

    print("\nDone.")
    print("Next step: start the app; it will recreate tables from the models.")
    print(f"Database location: {DB_PATH}")


if __name__ == "__main__":
    main()
