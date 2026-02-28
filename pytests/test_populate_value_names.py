from __future__ import annotations

import importlib
import json
from io import StringIO
from pathlib import Path

import pytest

from models.dates import DateEntry
from models.entities import Entity
from models.units import Unit
from models.value_names import ValueName
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


def _load_script_module():
    # Import the script as a module so we can unit-test helpers.
    return importlib.import_module("utils.populate_value_names")


def test_normalize_cik():
    m = _load_script_module()
    assert m._normalize_cik(1750) == "0000001750"
    assert m._normalize_cik("0000000003") == "0000000003"
    assert m._normalize_cik("CIK0000001750") == "0000001750"
    assert m._normalize_cik(None) is None


def test_parse_ymd():
    m = _load_script_module()
    d = m._parse_ymd("2024-01-02")
    assert d is not None
    assert str(d) == "2024-01-02"
    assert m._parse_ymd("not-a-date") is None


def test_get_or_create_helpers_are_idempotent(tmp_db_session):
    session, _engine = tmp_db_session
    m = _load_script_module()

    e1 = m._get_or_create_entity(session, "0000001750", company_name="AAR CORP.")
    e2 = m._get_or_create_entity(session, "0000001750", company_name="AAR CORP.")
    assert e1 == e2

    u1 = m._get_or_create_unit(session, "USD")
    u2 = m._get_or_create_unit(session, "USD")
    assert u1 == u2

    d1 = m._get_or_create_date_entry(session, "2010-05-31")
    d2 = m._get_or_create_date_entry(session, "2010-05-31")
    assert d1 == d2

    vn1 = m._get_or_create_value_name(session, "us-gaap.Assets", u1)
    vn2 = m._get_or_create_value_name(session, "us-gaap.Assets", u1)
    assert vn1 == vn2


def test_process_submissions_inserts_entities_dates_units_and_value_names(
    tmp_db_session, sample_submissions_dict, monkeypatch
):
    session, engine = tmp_db_session
    m = _load_script_module()

    # Direct the module to operate against the temp DB and temp raw_data.
    monkeypatch.setattr(m, "engine", engine, raising=False)
    monkeypatch.setattr(m, "Session", lambda **_: session, raising=False)

    # Provide exactly one submissions file via _iter_json_files.
    def fake_iter_json_files(_dir: str):
        yield "submissions_sample.json", "submissions_sample.json"

    monkeypatch.setattr(m, "_iter_json_files", fake_iter_json_files, raising=True)

    def fake_open(_path: str, *args, **kwargs):
        class _CM:
            def __enter__(self):
                # json.load expects a file-like object; we fake it by returning a
                # minimal object with read().
                return StringIO(json.dumps(sample_submissions_dict))

            def __exit__(self, exc_type, exc, tb):
                return False

        return _CM()

    monkeypatch.setattr(m, "open", fake_open, raising=False)

    counts = m._process_submissions(session)

    assert counts["files"] == 1
    assert session.query(Entity).count() >= 1
    assert session.query(Unit).filter_by(name="NA").count() == 1
    assert session.query(ValueName).count() >= 1
    assert session.query(DateEntry).count() >= 1


def test_process_companyfacts_inserts_units_value_names_and_dates(
    tmp_db_session, sample_companyfacts_dict, monkeypatch
):
    session, engine = tmp_db_session
    m = _load_script_module()

    monkeypatch.setattr(m, "engine", engine, raising=False)
    monkeypatch.setattr(m, "Session", lambda **_: session, raising=False)

    def fake_iter_json_files(_dir: str):
        yield "companyfacts_sample.json", "companyfacts_sample.json"

    monkeypatch.setattr(m, "_iter_json_files", fake_iter_json_files, raising=True)

    def fake_open(_path: str, *args, **kwargs):
        class _CM:
            def __enter__(self):
                return StringIO(json.dumps(sample_companyfacts_dict))

            def __exit__(self, exc_type, exc, tb):
                return False

        return _CM()

    monkeypatch.setattr(m, "open", fake_open, raising=False)

    counts = m._process_companyfacts(session)

    assert counts["files"] == 1
    # companyfacts sample contains USD unit and at least one date/end.
    assert session.query(Unit).count() >= 1
    assert session.query(ValueName).count() >= 1
    assert session.query(DateEntry).count() >= 1
