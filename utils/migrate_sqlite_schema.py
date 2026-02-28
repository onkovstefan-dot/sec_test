"""SQLite one-off migration helper.

This project does not use Alembic yet. For local development on SQLite,
changing SQLAlchemy models will *not* update existing tables.

Run this script to bring an existing `data/sec.db` in sync with current models.

It will:
- add new nullable columns when missing
- attempt limited type migrations (only when safe)

Note: SQLite has limited ALTER TABLE support. For complex migrations,
create a new DB or use a table-copy strategy.
"""

from __future__ import annotations

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sec.db")


def _existing_columns(cur: sqlite3.Cursor, table: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def add_column_if_missing(cur: sqlite3.Cursor, table: str, col: str, ddl: str) -> bool:
    cols = _existing_columns(cur, table)
    if col in cols:
        return False
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    return True


def main() -> None:
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"DB not found: {DB_PATH}")

    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()

        changed = False

        # entities: add metadata columns
        changed |= add_column_if_missing(cur, "entities", "company_name", "TEXT")
        changed |= add_column_if_missing(cur, "entities", "country", "TEXT")
        changed |= add_column_if_missing(cur, "entities", "sector", "TEXT")

        # value_names: ensure source exists (type changes require rebuild; just ensure column)
        # (If it already exists as INTEGER, SQLite is dynamic typed and will still store TEXT.)
        changed |= add_column_if_missing(cur, "value_names", "source", "TEXT")

        # daily_values: if value column exists as FLOAT, SQLite will still let you store TEXT.
        # No action required; keep here for visibility.

        if changed:
            con.commit()
            print("Migration applied successfully.")
        else:
            print("No changes needed; schema already up to date.")

    finally:
        con.close()


if __name__ == "__main__":
    main()
