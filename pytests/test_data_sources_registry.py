from __future__ import annotations

import sqlite3

from utils.migrate_sqlite_schema import (
    create_data_sources_table_if_missing,
    seed_data_sources_if_missing,
)


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,)
    )
    return cur.fetchone() is not None


def _rows(cur: sqlite3.Cursor) -> list[tuple[str, str]]:
    cur.execute("SELECT name, display_name FROM data_sources ORDER BY name")
    return [(r[0], r[1]) for r in cur.fetchall()]


def test_data_sources_table_and_seed_rows_are_idempotent(tmp_path) -> None:
    db_path = tmp_path / "ds.sqlite"
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()

        changed_create = create_data_sources_table_if_missing(cur)
        assert changed_create is True
        assert _table_exists(cur, "data_sources")

        changed_seed = seed_data_sources_if_missing(cur)
        assert changed_seed is True
        con.commit()

        rows1 = _rows(cur)
        assert ("sec", "SEC EDGAR") in rows1
        assert ("gleif", "GLEIF") in rows1

        # Idempotent.
        assert create_data_sources_table_if_missing(cur) is False
        assert seed_data_sources_if_missing(cur) is False

        rows2 = _rows(cur)
        assert rows1 == rows2

    finally:
        con.close()
