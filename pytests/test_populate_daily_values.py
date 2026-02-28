from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from pytests.common import create_empty_sqlite_db


@pytest.fixture()
def tmp_db_session(tmp_path):
    session, engine = create_empty_sqlite_db(tmp_path / "test_sec.db")
    try:
        yield session, engine
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def sample_companyfacts_dict() -> dict:
    p = Path(__file__).resolve().parents[1] / "test_data" / "companyfacts_sample.json"
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture()
def sample_submissions_dict() -> dict:
    p = Path(__file__).resolve().parents[1] / "test_data" / "submissions_sample.json"
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture()
def sample_submissions_missing_dates_dict() -> dict:
    p = (
        Path(__file__).resolve().parents[1]
        / "test_data"
        / "submissions_missing_dates_sample.json"
    )
    return json.loads(p.read_text(encoding="utf-8"))


def _load_script_module():
    # Import the script as a module so we can unit-test helpers.
    return importlib.import_module("utils.populate_daily_values")


def test_normalize_cik(sample_companyfacts_dict):
    m = _load_script_module()
    assert m._normalize_cik(1750) == "0000001750"
    assert m._normalize_cik("0000000003") == "0000000003"
    assert m._normalize_cik("CIK0000001750") == "0000001750"
    assert m._normalize_cik(None) is None


def test_extract_entity_identity_prefers_payload_but_falls_back_to_filename(
    sample_companyfacts_dict,
):
    m = _load_script_module()
    cik, name = m.extract_entity_identity(
        sample_companyfacts_dict, "CIK0000001750.json"
    )
    assert cik == "0000001750"
    assert name == "AAR CORP."

    cik2, name2 = m.extract_entity_identity({"entityName": "X"}, "CIK0000009999.json")
    assert cik2 == "0000009999"
    assert name2 == "X"


def test_iter_companyfacts_points(sample_companyfacts_dict):
    m = _load_script_module()
    pts = list(m.iter_companyfacts_points(sample_companyfacts_dict["facts"]))
    assert ("us-gaap.Assets", "USD", "2010-05-31", 1501042000) in pts


def test_resolve_recent_payload_and_iter_submissions_points(sample_submissions_dict):
    m = _load_script_module()
    schema, recent = m._resolve_recent_payload(sample_submissions_dict)
    assert schema == "full_submissions"
    assert isinstance(recent, dict)

    pts = list(m.iter_submissions_recent_points(recent))
    # form should yield with filingDate
    assert any(p[0] == "submissions.recent.form" and p[2] == "2024-01-02" for p in pts)


def test_process_companyfacts_file_inserts_daily_value(
    tmp_db_session, sample_companyfacts_dict, monkeypatch
):
    session, engine = tmp_db_session
    m = _load_script_module()

    # Patch the script's global session/engine to the temp test DB.
    monkeypatch.setattr(m, "engine", engine, raising=False)
    monkeypatch.setattr(m, "session", session, raising=False)

    # Ensure NA unit exists and caches behave.
    unit_id = m.get_or_create_unit("NA").id

    entity = m.get_or_create_entity("0000001750", company_name="AAR CORP.")

    # Minimal caches for processor
    unit_cache = {}
    value_name_cache = {}
    date_cache = {}

    def get_unit_id_cached(name):
        key = (name or "NA").strip() or "NA"
        if key in unit_cache:
            return unit_cache[key]
        unit_cache[key] = m.get_or_create_unit(key).id
        return unit_cache[key]

    def get_value_name_id_cached(name, unit_id):
        key = (name, unit_id)
        if key in value_name_cache:
            return value_name_cache[key]
        value_name_cache[key] = m.get_or_create_value_name(name, unit_id=unit_id).id
        return value_name_cache[key]

    def get_date_id_cached(date_str):
        if date_str in date_cache:
            return date_cache[date_str]
        de = m.get_or_create_date_entry(date_str)
        date_cache[date_str] = de.id
        return de.id

    planned, dups = m.process_companyfacts_file(
        data=sample_companyfacts_dict,
        source="companyfacts",
        filename="companyfacts_sample.json",
        entity_id=entity.id,
        get_unit_id_cached=get_unit_id_cached,
        get_value_name_id_cached=get_value_name_id_cached,
        get_date_id_cached=get_date_id_cached,
    )
    assert planned == 1
    assert dups == 0

    session.commit()
    from models.daily_values import DailyValue

    assert session.query(DailyValue).count() == 1


def test_process_submissions_file_returns_unprocessed_reason_when_dates_missing(
    tmp_db_session, sample_submissions_missing_dates_dict, monkeypatch
):
    session, engine = tmp_db_session
    m = _load_script_module()

    # Patch global session/engine to temp DB.
    monkeypatch.setattr(m, "engine", engine, raising=False)
    monkeypatch.setattr(m, "session", session, raising=False)

    entity = m.get_or_create_entity("0000000013", company_name="SAMPLE")

    # Minimal cache fns
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

    schema, planned, dups, reason = m.process_submissions_file(
        data=sample_submissions_missing_dates_dict,
        source="submissions",
        filename="submissions_missing_dates_sample.json",
        entity_id=entity.id,
        get_unit_id_cached=get_unit_id_cached,
        get_value_name_id_cached=get_value_name_id_cached,
        get_date_id_cached=get_date_id_cached,
    )

    assert schema == "full_submissions"
    assert planned == 0
    assert dups == 0
    assert reason == "submissions_missing_dates"


def test_main_end_to_end_discovers_and_processes_two_files(tmp_db_session, monkeypatch):
    session, engine = tmp_db_session
    m = _load_script_module()

    monkeypatch.setattr(m, "engine", engine, raising=False)
    monkeypatch.setattr(m, "session", session, raising=False)

    # Force discovery to only return our two fixture files.
    root = Path(__file__).resolve().parents[1] / "test_data"
    cpath = str(root / "companyfacts_sample.json")
    spath = str(root / "submissions_sample.json")

    def fake_discover(_root_dir: str):
        return [
            ("companyfacts", cpath, "CIK0000001750.json"),
            ("submissions", spath, "CIK0000000003.json"),
        ]

    monkeypatch.setattr(m, "discover_json_files", fake_discover, raising=True)
    monkeypatch.setattr(m, "RAW_DATA_DIR", str(root), raising=False)

    m.main()

    from models.daily_values import DailyValue
    from models.value_names import ValueName
    from models.units import Unit

    # Assets + submissions.recent.form + submissions.recent.accessionNumber + submissions.recent.primaryDocument
    assert session.query(DailyValue).count() >= 2
    assert session.query(ValueName).count() >= 2
    assert session.query(Unit).count() >= 1
