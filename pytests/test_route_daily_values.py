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

    # Seed minimal data so the page can render.
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


def test_daily_values_requires_entity_id(client):
    c, _entity_id = client
    resp = c.get("/daily-values")
    assert resp.status_code == 400
    assert resp.content_type.startswith("text/plain")
    assert "entity_id" in resp.get_data(as_text=True)


def test_daily_values_404_for_unknown_entity(client):
    c, _entity_id = client
    resp = c.get("/daily-values?entity_id=999999")
    assert resp.status_code == 404


def test_daily_values_renders_html(client):
    c, entity_id = client
    resp = c.get(f"/daily-values?entity_id={entity_id}")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/html")

    html = resp.get_data(as_text=True)
    assert "Assets" in html
    assert "USD" in html


def test_daily_values_json_mode(client):
    c, entity_id = client
    resp = c.get(
        f"/daily-values?entity_id={entity_id}", headers={"Accept": "application/json"}
    )
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/json")

    data = resp.get_json()
    assert isinstance(data, dict)
    assert data.get("entity_id") == entity_id
    assert isinstance(data.get("rows"), list)
    assert data["rows"], "expected at least one row"

    row = data["rows"][0]
    for k in ("date", "value_name", "unit", "value"):
        assert k in row
