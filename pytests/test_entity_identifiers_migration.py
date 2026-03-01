from __future__ import annotations

import sqlite3

from utils.migrate_sqlite_schema import migrate_entity_identifiers_audit_columns


def _cols(cur: sqlite3.Cursor, table: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def test_migrate_entity_identifiers_audit_columns_adds_columns(tmp_path) -> None:
    db_path = tmp_path / "m.sqlite"

    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE entity_identifiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id INTEGER NOT NULL,
                scheme TEXT NOT NULL,
                value TEXT NOT NULL
            );
            """.strip()
        )
        con.commit()

        changed = migrate_entity_identifiers_audit_columns(cur)
        assert changed is True
        con.commit()

        cols = _cols(cur, "entity_identifiers")
        assert {"confidence", "added_at", "last_seen_at"}.issubset(cols)

        # Idempotent
        changed2 = migrate_entity_identifiers_audit_columns(cur)
        assert changed2 is False

    finally:
        con.close()
