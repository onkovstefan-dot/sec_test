from __future__ import annotations

import sqlite3

from utils.migrate_sqlite_schema import migrate_file_processing_tracking_columns


def _cols(cur: sqlite3.Cursor, table: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def test_migrate_file_processing_tracking_columns_adds_columns(tmp_path) -> None:
    db_path = tmp_path / "m.sqlite"

    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE file_processing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id INTEGER NOT NULL,
                source_file TEXT NOT NULL,
                processed_at DATETIME NOT NULL
            );
            """.strip()
        )
        con.commit()

        changed = migrate_file_processing_tracking_columns(cur)
        assert changed is True
        con.commit()

        cols = _cols(cur, "file_processing")
        assert {"source", "record_count"}.issubset(cols)

        # Idempotent
        changed2 = migrate_file_processing_tracking_columns(cur)
        assert changed2 is False

    finally:
        con.close()
