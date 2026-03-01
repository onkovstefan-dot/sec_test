"""SQLite one-off migration helper.

This project does not use Alembic yet. For local development on SQLite,
changing SQLAlchemy models will *not* update existing tables.

Run this script to bring an existing `data/sec.db` in sync with current models.

It will:
- add new nullable columns when missing
- attempt limited type migrations (only when safe)
- create a small set of indexes used by the app's hot paths

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


def create_index_if_missing(cur: sqlite3.Cursor, *, name: str, ddl: str) -> bool:
    """Create an index if it does not already exist.

    Args:
        name: Index name to check in sqlite_master.
        ddl: Full CREATE INDEX statement.
    """

    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=? LIMIT 1", (name,)
    )
    if cur.fetchone():
        return False
    cur.execute(ddl)
    return True


def main() -> None:
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"DB not found: {DB_PATH}")

    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()

        changed = False

        # entity_metadata: add new metadata columns
        changed |= add_column_if_missing(cur, "entity_metadata", "sic", "TEXT")
        changed |= add_column_if_missing(
            cur, "entity_metadata", "sic_description", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "state_of_incorporation", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "fiscal_year_end", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "filer_category", "TEXT"
        )
        changed |= add_column_if_missing(cur, "entity_metadata", "entity_type", "TEXT")
        changed |= add_column_if_missing(cur, "entity_metadata", "website", "TEXT")
        changed |= add_column_if_missing(cur, "entity_metadata", "phone", "TEXT")
        changed |= add_column_if_missing(cur, "entity_metadata", "ein", "TEXT")
        changed |= add_column_if_missing(cur, "entity_metadata", "tickers", "TEXT")
        changed |= add_column_if_missing(cur, "entity_metadata", "exchanges", "TEXT")
        changed |= add_column_if_missing(
            cur, "entity_metadata", "business_street1", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "business_street2", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "business_city", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "business_state", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "business_zipcode", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "business_country", "TEXT"
        )

        # Additional fields from submissions analysis
        changed |= add_column_if_missing(cur, "entity_metadata", "lei", "TEXT")
        changed |= add_column_if_missing(
            cur, "entity_metadata", "investor_website", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "entity_description", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "owner_organization", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "state_of_incorporation_description", "TEXT"
        )
        changed |= add_column_if_missing(cur, "entity_metadata", "sec_flags", "TEXT")
        changed |= add_column_if_missing(
            cur, "entity_metadata", "has_insider_transactions_as_owner", "INTEGER"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "has_insider_transactions_as_issuer", "INTEGER"
        )

        # Mailing address fields
        changed |= add_column_if_missing(
            cur, "entity_metadata", "mailing_street1", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "mailing_street2", "TEXT"
        )
        changed |= add_column_if_missing(cur, "entity_metadata", "mailing_city", "TEXT")
        changed |= add_column_if_missing(
            cur, "entity_metadata", "mailing_state", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "mailing_zipcode", "TEXT"
        )
        changed |= add_column_if_missing(
            cur, "entity_metadata", "mailing_country", "TEXT"
        )

        # Former names (stored as JSON)
        changed |= add_column_if_missing(cur, "entity_metadata", "former_names", "TEXT")

        # entities: add metadata columns (legacy - now moved to entity_metadata table)
        changed |= add_column_if_missing(cur, "entities", "company_name", "TEXT")
        changed |= add_column_if_missing(cur, "entities", "country", "TEXT")
        changed |= add_column_if_missing(cur, "entities", "sector", "TEXT")

        # value_names: ensure source exists (type changes require rebuild; just ensure column)
        # (If it already exists as INTEGER, SQLite is dynamic typed and will still store TEXT.)
        changed |= add_column_if_missing(cur, "value_names", "source", "TEXT")

        # daily_values: if value column exists as FLOAT, SQLite will still let you store TEXT.
        # No action required; keep here for visibility.

        # --- indexes (hot paths) ---
        # /check-cik uses a join on daily_values.entity_id and sorts by entities.cik.
        # /daily-values filters by daily_values.entity_id.
        # /check-cik cards load metadata by entity_metadata.entity_id.
        changed |= create_index_if_missing(
            cur,
            name="ix_daily_values_entity_id",
            ddl="CREATE INDEX ix_daily_values_entity_id ON daily_values(entity_id)",
        )
        changed |= create_index_if_missing(
            cur,
            name="ix_entities_cik",
            ddl="CREATE INDEX ix_entities_cik ON entities(cik)",
        )
        changed |= create_index_if_missing(
            cur,
            name="ix_entity_metadata_entity_id",
            ddl="CREATE INDEX ix_entity_metadata_entity_id ON entity_metadata(entity_id)",
        )

        if changed:
            con.commit()
            print("Migration applied successfully.")
        else:
            print("No changes needed; schema already up to date.")

    finally:
        con.close()


if __name__ == "__main__":
    main()
