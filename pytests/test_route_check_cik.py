from __future__ import annotations

import datetime as dt

import pytest

from app import create_app
from pytests.common import create_empty_sqlite_db, patch_app_db

from models.daily_values import DailyValue
from models.dates import DateEntry
from models.entities import Entity
from models.units import Unit
from models.value_names import ValueName


@pytest.fixture()
def client(tmp_path, monkeypatch):
    session, engine = create_empty_sqlite_db(tmp_path / "test.sqlite")
    patch_app_db(monkeypatch, engine)

    # Entity with one DailyValue so it appears in the dropdown and redirects.
    entity = Entity(cik="0000000001")
    session.add(entity)
    session.flush()

    date = DateEntry(date=dt.date(2020, 1, 1))
    unit = Unit(name="USD")
    vn = ValueName(name="Assets")
    session.add_all([date, unit, vn])
    session.flush()

    session.add(
        DailyValue(
            entity_id=entity.id,
            date_id=date.id,
            value_name_id=vn.id,
            unit_id=unit.id,
            value=123,
        )
    )
    session.commit()
    session.close()

    app = create_app()
    return app.test_client(), entity.id


def test_check_cik_page_renders(client):
    c, _entity_id = client
    resp = c.get("/check-cik")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/html")
    # UI wording
    assert b"Select Company" in resp.data


def test_check_cik_redirects_when_data_exists(client):
    c, _entity_id = client
    resp = c.get("/check-cik?cik=1", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/daily-values" in resp.headers.get("Location", "")
