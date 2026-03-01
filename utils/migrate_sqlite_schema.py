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


def create_table_if_missing(cur: sqlite3.Cursor, *, table: str, ddl: str) -> bool:
    """Create a table if it does not already exist.

    Args:
        table: Table name.
        ddl: Full CREATE TABLE statement.

    Returns:
        True if created, False if already exists.
    """
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,)
    )
    if cur.fetchone():
        return False
    cur.execute(ddl)
    return True


def create_data_sources_table_if_missing(cur: sqlite3.Cursor) -> bool:
    """Idempotently create the data_sources registry table."""

    ddl = """
    CREATE TABLE data_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        display_name TEXT NULL,
        description TEXT NULL,
        created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        CONSTRAINT uq_data_sources_name UNIQUE (name)
    );
    """.strip()

    return create_table_if_missing(cur, table="data_sources", ddl=ddl)


def seed_data_sources_if_missing(cur: sqlite3.Cursor) -> bool:
    """Seed initial canonical sources.

    Uses INSERT OR IGNORE so it is safe to re-run.

    Seed set is intentionally small; add to it as new sources are integrated.
    """

    # If table does not exist yet, nothing to do.
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        ("data_sources",),
    )
    if cur.fetchone() is None:
        return False

    before = cur.execute("SELECT COUNT(*) FROM data_sources").fetchone()[0]

    cur.executemany(
        """
        INSERT OR IGNORE INTO data_sources(name, display_name, description)
        VALUES(?, ?, ?)
        """.strip(),
        [
            ("sec", "SEC EDGAR", "US SEC EDGAR filings and XBRL-derived facts"),
            ("gleif", "GLEIF", "Global Legal Entity Identifier Foundation"),
        ],
    )

    after = cur.execute("SELECT COUNT(*) FROM data_sources").fetchone()[0]
    return after != before


def create_entity_relationships_table_if_missing(cur: sqlite3.Cursor) -> bool:
    """Idempotently create the entity_relationships table."""

    # Note: SQLite only enforces FK constraints if PRAGMA foreign_keys=ON.
    ddl = """
    CREATE TABLE entity_relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_entity_id INTEGER NOT NULL,
        child_entity_id INTEGER NOT NULL,
        relationship_type TEXT NOT NULL,
        ownership_pct REAL NULL,
        effective_from DATE NULL,
        effective_to DATE NULL,
        source TEXT NULL,
        CONSTRAINT uq_entity_relationships_parent_child_type
            UNIQUE (parent_entity_id, child_entity_id, relationship_type),
        FOREIGN KEY(parent_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
        FOREIGN KEY(child_entity_id) REFERENCES entities(id) ON DELETE CASCADE
    );
    """.strip()

    changed = create_table_if_missing(cur, table="entity_relationships", ddl=ddl)

    # Useful indexes for lookups.
    changed |= create_index_if_missing(
        cur,
        name="ix_entity_relationships_parent_entity_id",
        ddl=(
            "CREATE INDEX ix_entity_relationships_parent_entity_id "
            "ON entity_relationships(parent_entity_id)"
        ),
    )
    changed |= create_index_if_missing(
        cur,
        name="ix_entity_relationships_child_entity_id",
        ddl=(
            "CREATE INDEX ix_entity_relationships_child_entity_id "
            "ON entity_relationships(child_entity_id)"
        ),
    )

    return changed


def create_sec_filings_table_if_missing(cur: sqlite3.Cursor) -> bool:
    """Idempotently create the sec_filings table."""

    ddl = """
    CREATE TABLE sec_filings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_id INTEGER NOT NULL,
        accession_number TEXT NOT NULL,
        form_type TEXT NOT NULL,
        filing_date DATE NULL,
        report_date DATE NULL,
        primary_document TEXT NULL,
        index_url TEXT NULL,
        document_url TEXT NULL,
        full_text_url TEXT NULL,
        fetched_at DATETIME NULL,
        fetch_status TEXT NOT NULL DEFAULT 'pending',
        source TEXT NOT NULL DEFAULT 'sec_submissions_local',
        CONSTRAINT uq_sec_filings_entity_accession
            UNIQUE (entity_id, accession_number),
        FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE
    );
    """.strip()

    changed = create_table_if_missing(cur, table="sec_filings", ddl=ddl)

    changed |= create_index_if_missing(
        cur,
        name="ix_sec_filings_entity_id",
        ddl="CREATE INDEX ix_sec_filings_entity_id ON sec_filings(entity_id)",
    )
    changed |= create_index_if_missing(
        cur,
        name="ix_sec_filings_accession_number",
        ddl=(
            "CREATE INDEX ix_sec_filings_accession_number "
            "ON sec_filings(accession_number)"
        ),
    )

    return changed


def create_sec_tickers_table_if_missing(cur: sqlite3.Cursor) -> bool:
    """Idempotently create the sec_tickers table."""

    ddl = """
    CREATE TABLE sec_tickers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_id INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        exchange TEXT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        source TEXT NOT NULL DEFAULT 'sec_submissions_local',
        CONSTRAINT uq_sec_tickers_ticker_exchange
            UNIQUE (ticker, exchange),
        FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE
    );
    """.strip()

    changed = create_table_if_missing(cur, table="sec_tickers", ddl=ddl)

    changed |= create_index_if_missing(
        cur,
        name="ix_sec_tickers_entity_id",
        ddl="CREATE INDEX ix_sec_tickers_entity_id ON sec_tickers(entity_id)",
    )
    changed |= create_index_if_missing(
        cur,
        name="ix_sec_tickers_ticker",
        ddl="CREATE INDEX ix_sec_tickers_ticker ON sec_tickers(ticker)",
    )
    changed |= create_index_if_missing(
        cur,
        name="ix_sec_tickers_exchange",
        ddl="CREATE INDEX ix_sec_tickers_exchange ON sec_tickers(exchange)",
    )

    return changed


def create_sec_filing_documents_table_if_missing(cur: sqlite3.Cursor) -> bool:
    """Idempotently create the sec_filing_documents table."""

    ddl = """
    CREATE TABLE sec_filing_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filing_id INTEGER NOT NULL,
        doc_type TEXT NOT NULL,
        filename TEXT NULL,
        local_path TEXT NULL,
        url TEXT NULL,
        size_bytes INTEGER NULL,
        fetched_at DATETIME NULL,
        fetch_status TEXT NOT NULL DEFAULT 'pending',
        CONSTRAINT uq_sec_filing_documents_filing_doc_type
            UNIQUE (filing_id, doc_type),
        FOREIGN KEY(filing_id) REFERENCES sec_filings(id) ON DELETE CASCADE
    );
    """.strip()

    changed = create_table_if_missing(cur, table="sec_filing_documents", ddl=ddl)

    changed |= create_index_if_missing(
        cur,
        name="ix_sec_filing_documents_filing_id",
        ddl=(
            "CREATE INDEX ix_sec_filing_documents_filing_id "
            "ON sec_filing_documents(filing_id)"
        ),
    )

    return changed


def migrate_entity_identifiers_audit_columns(cur: sqlite3.Cursor) -> bool:
    """Add auditability columns to entity_identifiers (idempotent).

    - confidence: TEXT NOT NULL DEFAULT 'authoritative'
    - added_at: DATETIME NOT NULL DEFAULT (UTC timestamp at insert time)
    - last_seen_at: DATETIME NULL

    Note: SQLite cannot use Python callables as DEFAULTs in ALTER TABLE.
    We use SQLite's CURRENT_TIMESTAMP which is UTC.
    """

    changed = False
    changed |= add_column_if_missing(
        cur,
        "entity_identifiers",
        "confidence",
        "TEXT NOT NULL DEFAULT 'authoritative'",
    )
    changed |= add_column_if_missing(
        cur,
        "entity_identifiers",
        "added_at",
        "DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)",
    )
    changed |= add_column_if_missing(
        cur,
        "entity_identifiers",
        "last_seen_at",
        "DATETIME NULL",
    )
    return changed


def migrate_file_processing_tracking_columns(cur: sqlite3.Cursor) -> bool:
    """Add tracking columns to file_processing (idempotent).

    - source: TEXT NOT NULL DEFAULT 'local'
    - record_count: INTEGER NULL
    """

    changed = False
    changed |= add_column_if_missing(
        cur,
        "file_processing",
        "source",
        "TEXT NOT NULL DEFAULT 'local'",
    )
    changed |= add_column_if_missing(
        cur,
        "file_processing",
        "record_count",
        "INTEGER NULL",
    )
    return changed


def migrate_multisource_schema_columns(cur: sqlite3.Cursor) -> bool:
    """Add multi-source / traceability columns (idempotent)."""

    changed = False

    # value_names
    changed |= add_column_if_missing(cur, "value_names", "namespace", "TEXT NULL")

    # daily_values
    changed |= add_column_if_missing(cur, "daily_values", "source", "TEXT NULL")
    changed |= add_column_if_missing(cur, "daily_values", "period_type", "TEXT NULL")
    changed |= add_column_if_missing(
        cur,
        "daily_values",
        "start_date_id",
        "INTEGER NULL REFERENCES dates(id)",
    )
    changed |= add_column_if_missing(
        cur,
        "daily_values",
        "accession_number",
        "TEXT NULL",
    )

    # entity_metadata
    changed |= add_column_if_missing(
        cur, "entity_metadata", "data_sources", "TEXT NULL"
    )
    changed |= add_column_if_missing(
        cur,
        "entity_metadata",
        "last_sec_sync_at",
        "DATETIME NULL",
    )

    return changed


def main() -> None:
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"DB not found: {DB_PATH}")

    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()

        changed = False

        # --- new tables ---
        changed |= create_data_sources_table_if_missing(cur)
        changed |= create_entity_relationships_table_if_missing(cur)
        changed |= create_sec_filings_table_if_missing(cur)
        changed |= create_sec_tickers_table_if_missing(cur)
        changed |= create_sec_filing_documents_table_if_missing(cur)

        # Seed lookup tables.
        changed |= seed_data_sources_if_missing(cur)

        # --- column migrations ---
        changed |= migrate_entity_identifiers_audit_columns(cur)
        changed |= migrate_file_processing_tracking_columns(cur)
        changed |= migrate_multisource_schema_columns(cur)

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
