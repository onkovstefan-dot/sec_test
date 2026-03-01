from __future__ import annotations

import sqlite3

from utils.migrate_sqlite_schema import migrate_multisource_schema_columns


def _cols(cur: sqlite3.Cursor, table: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def test_multisource_migrations_apply_to_empty_and_seeded_db(tmp_path) -> None:
    empty_db = tmp_path / "empty.sqlite"

    # Build a minimal "empty" DB: tables exist but without the new columns.
    con = sqlite3.connect(empty_db)
    try:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE value_names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
            """.strip()
        )
        cur.execute(
            """
            CREATE TABLE dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL
            );
            """.strip()
        )
        cur.execute(
            """
            CREATE TABLE daily_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id INTEGER NOT NULL,
                date_id INTEGER NOT NULL,
                value_name_id INTEGER NOT NULL,
                value TEXT
            );
            """.strip()
        )
        cur.execute(
            """
            CREATE TABLE entity_metadata (
                entity_id INTEGER PRIMARY KEY,
                company_name TEXT NULL
            );
            """.strip()
        )
        con.commit()

        changed = migrate_multisource_schema_columns(cur)
        assert changed is True
        con.commit()

        assert {"namespace"}.issubset(_cols(cur, "value_names"))
        assert {"source", "period_type", "start_date_id", "accession_number"}.issubset(
            _cols(cur, "daily_values")
        )
        assert {"data_sources", "last_sec_sync_at"}.issubset(
            _cols(cur, "entity_metadata")
        )

        # Idempotent
        changed2 = migrate_multisource_schema_columns(cur)
        assert changed2 is False

    finally:
        con.close()

    # Seeded DB case: same tables but with some pre-existing rows.
    seeded_db = tmp_path / "seeded.sqlite"
    con2 = sqlite3.connect(seeded_db)
    try:
        cur2 = con2.cursor()
        cur2.execute(
            """
            CREATE TABLE value_names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'sec'
            );
            """.strip()
        )
        cur2.execute(
            "INSERT INTO value_names(name, source) VALUES('us-gaap.Assets','sec')"
        )

        cur2.execute(
            """
            CREATE TABLE dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL
            );
            """.strip()
        )
        cur2.execute("INSERT INTO dates(date) VALUES('2024-01-01')")

        cur2.execute(
            """
            CREATE TABLE daily_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id INTEGER NOT NULL,
                date_id INTEGER NOT NULL,
                value_name_id INTEGER NOT NULL,
                value TEXT
            );
            """.strip()
        )
        cur2.execute(
            "INSERT INTO daily_values(entity_id, date_id, value_name_id, value) VALUES(1,1,1,'123')"
        )

        cur2.execute(
            """
            CREATE TABLE entity_metadata (
                entity_id INTEGER PRIMARY KEY,
                company_name TEXT NULL
            );
            """.strip()
        )
        cur2.execute(
            "INSERT INTO entity_metadata(entity_id, company_name) VALUES(1,'X')"
        )
        con2.commit()

        changed_seeded = migrate_multisource_schema_columns(cur2)
        assert changed_seeded is True
        con2.commit()

        assert {"namespace"}.issubset(_cols(cur2, "value_names"))
        assert {"source", "period_type", "start_date_id", "accession_number"}.issubset(
            _cols(cur2, "daily_values")
        )
        assert {"data_sources", "last_sec_sync_at"}.issubset(
            _cols(cur2, "entity_metadata")
        )

        # Existing row should still exist.
        cur2.execute("SELECT COUNT(*) FROM daily_values")
        assert cur2.fetchone()[0] == 1

    finally:
        con2.close()
