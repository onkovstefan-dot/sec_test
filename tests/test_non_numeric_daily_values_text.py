import sqlite3
from pathlib import Path

import pytest


def test_daily_values_text_schema_and_insert_roundtrip(tmp_path: Path):
    """Ensure `daily_values_text` can store non-numeric values.

    This is a lightweight integration test that uses SQLite directly to avoid
    importing the full app/session wiring.
    """

    db_path = tmp_path / "test.db"
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Minimal schema compatible with the project tables.
    cur.execute(
        "CREATE TABLE entities (id INTEGER PRIMARY KEY AUTOINCREMENT, cik TEXT NOT NULL)"
    )
    cur.execute(
        "CREATE TABLE dates (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL)"
    )
    cur.execute(
        "CREATE TABLE value_names (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, source INTEGER NOT NULL, added_on TEXT NOT NULL)"
    )
    cur.execute(
        "CREATE TABLE daily_values_text (\n"
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "  entity_id INTEGER NOT NULL,\n"
        "  date_id INTEGER NOT NULL,\n"
        "  value_name_id INTEGER NOT NULL,\n"
        "  value_text TEXT,\n"
        "  CONSTRAINT uq_daily_values_text_entity_date_value UNIQUE (entity_id, date_id, value_name_id)\n"
        ")"
    )

    # Seed FK tables.
    cur.execute("INSERT INTO entities(cik) VALUES (?)", ("0000000001",))
    cur.execute("INSERT INTO dates(date) VALUES (?)", ("2026-01-01",))
    cur.execute(
        "INSERT INTO value_names(name, source, added_on) VALUES (?,?,?)",
        ("form", 1, "2026-01-01T00:00:00"),
    )
    con.commit()

    entity_id = cur.execute("SELECT id FROM entities").fetchone()[0]
    date_id = cur.execute("SELECT id FROM dates").fetchone()[0]
    value_name_id = cur.execute("SELECT id FROM value_names").fetchone()[0]

    # Insert a non-numeric (e.g. SEC form type).
    cur.execute(
        "INSERT INTO daily_values_text(entity_id, date_id, value_name_id, value_text) VALUES (?,?,?,?)",
        (entity_id, date_id, value_name_id, "10-K"),
    )
    con.commit()

    # Verify roundtrip
    got = cur.execute(
        "SELECT value_text FROM daily_values_text WHERE entity_id=? AND date_id=? AND value_name_id=?",
        (entity_id, date_id, value_name_id),
    ).fetchone()[0]
    assert got == "10-K"

    # Verify uniqueness constraint works
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute(
            "INSERT INTO daily_values_text(entity_id, date_id, value_name_id, value_text) VALUES (?,?,?,?)",
            (entity_id, date_id, value_name_id, "10-Q"),
        )
        con.commit()

    con.close()
