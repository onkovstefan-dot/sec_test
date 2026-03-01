from __future__ import annotations

import importlib
import json
from pathlib import Path

from models.entities import Entity
from models.file_processing import FileProcessing
from pytests.common import create_empty_sqlite_db


def _load_script_module():
    return importlib.import_module("utils.populate_daily_values")


def _load_fixture(name: str) -> dict:
    p = Path(__file__).resolve().parents[1] / "test_data" / name
    return json.loads(p.read_text(encoding="utf-8"))


def test_companyfacts_ingestion_marks_record_count(tmp_path, monkeypatch) -> None:
    session, engine = create_empty_sqlite_db(tmp_path / "fp_rc.sqlite")
    m = _load_script_module()

    # Patch script globals to the temp test DB.
    monkeypatch.setattr(m, "engine", engine, raising=False)
    monkeypatch.setattr(m, "session", session, raising=False)
    monkeypatch.setattr(m, "Session", lambda: session, raising=False)

    data = _load_fixture("companyfacts_sample.json")

    # Ensure entity exists (companyfacts identifies by cik in the payload).
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
        unit_cache[key] = m.get_or_create_unit(key, session=session).id
        return unit_cache[key]

    def get_value_name_id_cached(name: str, unit_id: int | None) -> int:
        key = (name, unit_id)
        if key in value_name_cache:
            return value_name_cache[key]
        value_name_cache[key] = m.get_or_create_value_name(
            name, unit_id=unit_id, session=session
        ).id
        return value_name_cache[key]

    def get_date_id_cached(date_str: str) -> int | None:
        if date_str in date_cache:
            return date_cache[date_str]
        de = m.get_or_create_date_entry(date_str, session=session)
        if not de:
            return None
        date_cache[date_str] = de.id
        return de.id

    planned, dups = m.process_companyfacts_file(
        data=data,
        source="companyfacts",
        filename="companyfacts_sample.json",
        entity_id=entity.id,
        get_unit_id_cached=get_unit_id_cached,
        get_value_name_id_cached=get_value_name_id_cached,
        get_date_id_cached=get_date_id_cached,
        session=session,
    )
    assert planned > 0

    # Mark file processed as the worker loop does.
    m._mark_file_processed(
        session,
        entity_id=entity.id,
        source_file="companyfacts:companyfacts_sample.json",
        source="local",
        record_count=planned,
    )
    session.commit()

    fp = session.query(FileProcessing).first()
    assert fp is not None
    assert fp.source == "local"
    assert fp.record_count == planned
    assert fp.record_count >= 1
