from __future__ import annotations

import datetime as dt
import sqlite3

import pytest

from models.entities import Entity
from models.sec_filings import SecFiling
from models.sec_tickers import SecTicker
from pytests.common import create_empty_sqlite_db
from utils.migrate_sqlite_schema import (
    create_sec_filings_table_if_missing,
    create_sec_tickers_table_if_missing,
)


def _tables(con: sqlite3.Connection) -> set[str]:
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {r[0] for r in cur.fetchall()}


def test_sec_tables_exist_on_fresh_db(tmp_path):
    session, engine = create_empty_sqlite_db(tmp_path / "fresh.sqlite")
    try:
        con = engine.raw_connection()
        try:
            tables = _tables(con)
            assert "sec_filings" in tables
            assert "sec_tickers" in tables
        finally:
            con.close()
    finally:
        session.close()
        engine.dispose()


def test_sec_tables_created_by_migration_helpers(tmp_path):
    # Create empty db file with just the core entities table.
    db_path = tmp_path / "migrate.sqlite"
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("CREATE TABLE entities (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        con.commit()

        cur = con.cursor()
        changed_1 = False
        changed_1 |= create_sec_filings_table_if_missing(cur)
        changed_1 |= create_sec_tickers_table_if_missing(cur)
        con.commit()

        assert changed_1 is True
        assert "sec_filings" in _tables(con)
        assert "sec_tickers" in _tables(con)

        # Idempotent re-run.
        changed_2 = False
        changed_2 |= create_sec_filings_table_if_missing(cur)
        changed_2 |= create_sec_tickers_table_if_missing(cur)
        assert changed_2 is False
    finally:
        con.close()


def test_sec_filings_insert_and_unique_constraint(tmp_path):
    session, engine = create_empty_sqlite_db(tmp_path / "filings.sqlite")
    try:
        e = Entity(cik="0000000001")
        session.add(e)
        session.flush()

        f1 = SecFiling(
            entity_id=e.id,
            accession_number="000000000100000001",
            form_type="10-K",
            filing_date=dt.date(2024, 1, 1),
        )
        session.add(f1)
        session.commit()

        f_dupe = SecFiling(
            entity_id=e.id,
            accession_number="000000000100000001",
            form_type="10-K",
        )
        session.add(f_dupe)
        with pytest.raises(Exception):
            session.commit()
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def test_sec_tickers_insert_and_unique_constraint(tmp_path):
    session, engine = create_empty_sqlite_db(tmp_path / "tickers.sqlite")
    try:
        e = Entity(cik="0000000001")
        session.add(e)
        session.flush()

        t1 = SecTicker(entity_id=e.id, ticker="AAPL", exchange="XNAS")
        session.add(t1)
        session.commit()

        t_dupe = SecTicker(entity_id=e.id, ticker="AAPL", exchange="XNAS")
        session.add(t_dupe)
        with pytest.raises(Exception):
            session.commit()
    finally:
        session.rollback()
        session.close()
        engine.dispose()
