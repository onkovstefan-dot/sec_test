from __future__ import annotations

import importlib
import json
from pathlib import Path

from models.entities import Entity
from models.entity_identifiers import EntityIdentifier
from models.sec_filings import SecFiling
from models.sec_tickers import SecTicker
from pytests.common import create_empty_sqlite_db


def _load_script_module():
    return importlib.import_module("utils.populate_daily_values")


def _load_fixture(name: str) -> dict:
    p = Path(__file__).resolve().parents[1] / "test_data" / name
    return json.loads(p.read_text(encoding="utf-8"))


def test_process_submissions_file_populates_sec_filings_and_is_idempotent(
    tmp_path, monkeypatch
):
    session, engine = create_empty_sqlite_db(tmp_path / "sec_struct.sqlite")
    m = _load_script_module()

    # Patch script globals to the temp test DB.
    monkeypatch.setattr(m, "engine", engine, raising=False)
    monkeypatch.setattr(m, "session", session, raising=False)
    monkeypatch.setattr(m, "Session", lambda: session, raising=False)

    data = _load_fixture("submissions_sample.json")

    # Create entity and ensure submissions processing has an entity_id.
    entity = Entity(cik="0000000003")
    session.add(entity)
    session.flush()

    # Minimal caches.
    unit_cache: dict[str, int] = {}
    value_name_cache: dict[tuple[str, int | None], int] = {}
    date_cache: dict[str, int] = {}

    def get_unit_id_cached(unit_name: str | None) -> int:
        key = (unit_name or "NA").strip() or "NA"
        if key in unit_cache:
            return unit_cache[key]
        unit_cache[key] = m.get_or_create_unit(key).id
        return unit_cache[key]

    def get_value_name_id_cached(name: str, unit_id: int | None) -> int:
        key = (name, unit_id)
        if key in value_name_cache:
            return value_name_cache[key]
        value_name_cache[key] = m.get_or_create_value_name(name, unit_id=unit_id).id
        return value_name_cache[key]

    def get_date_id_cached(date_str: str) -> int | None:
        if date_str in date_cache:
            return date_cache[date_str]
        de = m.get_or_create_date_entry(date_str)
        if not de:
            return None
        date_cache[date_str] = de.id
        return de.id

    # First run
    schema, planned, dups, reason = m.process_submissions_file(
        data=data,
        source="submissions",
        filename="submissions_sample.json",
        entity_id=entity.id,
        get_unit_id_cached=get_unit_id_cached,
        get_value_name_id_cached=get_value_name_id_cached,
        get_date_id_cached=get_date_id_cached,
        session=session,
    )
    assert schema == "full_submissions"
    assert reason is None

    assert session.query(SecFiling).count() == 1
    filing = session.query(SecFiling).first()
    assert filing is not None
    assert filing.entity_id == entity.id
    assert filing.accession_number == "000000000324000001"  # dashes removed
    assert filing.form_type == "N-PORT"
    assert filing.index_url and "sec.gov/Archives/edgar/data/" in filing.index_url

    # Second run should be idempotent for sec_filings.
    schema2, planned2, dups2, reason2 = m.process_submissions_file(
        data=data,
        source="submissions",
        filename="submissions_sample.json",
        entity_id=entity.id,
        get_unit_id_cached=get_unit_id_cached,
        get_value_name_id_cached=get_value_name_id_cached,
        get_date_id_cached=get_date_id_cached,
        session=session,
    )
    assert schema2 == "full_submissions"
    assert reason2 is None
    assert session.query(SecFiling).count() == 1


def test_process_submissions_file_populates_sec_tickers_and_entity_identifiers(
    tmp_path, monkeypatch
):
    session, engine = create_empty_sqlite_db(tmp_path / "sec_tickers.sqlite")
    m = _load_script_module()

    monkeypatch.setattr(m, "engine", engine, raising=False)
    monkeypatch.setattr(m, "session", session, raising=False)
    monkeypatch.setattr(m, "Session", lambda: session, raising=False)

    # Minimal payload with tickers+exchanges.
    data = {
        "cik": "0000000003",
        "name": "X",
        "tickers": ["AAPL"],
        "exchanges": ["XNAS"],
        "filings": {
            "recent": {
                "filingDate": ["2024-01-02"],
                "form": ["10-K"],
                "accessionNumber": ["0000000003-24-000001"],
            }
        },
    }

    entity = Entity(cik="0000000003")
    session.add(entity)
    session.flush()

    # Reuse cache helpers from module by minimal stubs.
    def get_unit_id_cached(_):
        return m.get_or_create_unit("NA").id

    def get_value_name_id_cached(name, unit_id):
        return m.get_or_create_value_name(name, unit_id=unit_id).id

    def get_date_id_cached(date_str):
        de = m.get_or_create_date_entry(date_str)
        return de.id if de else None

    m.process_submissions_file(
        data=data,
        source="submissions",
        filename="inline.json",
        entity_id=entity.id,
        get_unit_id_cached=get_unit_id_cached,
        get_value_name_id_cached=get_value_name_id_cached,
        get_date_id_cached=get_date_id_cached,
        session=session,
    )

    assert session.query(SecTicker).count() == 1
    t = session.query(SecTicker).first()
    assert t is not None
    assert t.ticker == "AAPL"
    assert t.exchange == "XNAS"

    # Also created identity mapping.
    ident = (
        session.query(EntityIdentifier)
        .filter_by(scheme="ticker_exchange", value="AAPL:XNAS")
        .first()
    )
    assert ident is not None
    assert ident.entity_id == entity.id
