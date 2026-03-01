from __future__ import annotations

import sqlite3

from utils.migrate_sqlite_schema import create_sec_filing_documents_table_if_missing


def test_create_sec_filing_documents_table_if_missing(tmp_path) -> None:
    db_path = tmp_path / "m.sqlite"

    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()

        # Needs parent table for FK.
        cur.execute(
            """
            CREATE TABLE sec_filings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id INTEGER NOT NULL,
                accession_number TEXT NOT NULL,
                form_type TEXT NOT NULL
            );
            """.strip()
        )
        con.commit()

        changed = create_sec_filing_documents_table_if_missing(cur)
        assert changed is True
        con.commit()

        # Idempotent
        changed2 = create_sec_filing_documents_table_if_missing(cur)
        assert changed2 is False

        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sec_filing_documents'"
        )
        assert cur.fetchone() is not None

    finally:
        con.close()
