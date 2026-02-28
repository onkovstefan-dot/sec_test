from __future__ import annotations

from typing import Any

import pytest

from app import create_app
from pytests.common import create_empty_sqlite_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Create minimal DB rows so endpoints that touch DB can render.
    session, engine = create_empty_sqlite_db(tmp_path / "test_sec.db")

    # IMPORTANT: ensure the Flask app uses this temp DB (CI doesn't have data/sec.db).
    from pytests.common import patch_app_db

    patch_app_db(monkeypatch, engine)

    from datetime import date

    from models.entities import Entity
    from models.dates import DateEntry
    from models.units import Unit
    from models.value_names import ValueName
    from models.daily_values import DailyValue

    e = Entity(cik="0000000003")
    session.add(e)
    session.flush()

    d = DateEntry(date=date(2024, 1, 2))
    session.add(d)
    session.flush()

    u = Unit(name="NA")
    session.add(u)
    session.flush()

    # ValueName may or may not have unit_id depending on migrations; set only if present.
    vn_kwargs = {"name": "submissions.recent.form"}
    if hasattr(ValueName, "unit_id"):
        vn_kwargs["unit_id"] = u.id
    vn = ValueName(**vn_kwargs)
    session.add(vn)
    session.flush()

    dv = DailyValue(entity_id=e.id, date_id=d.id, value_name_id=vn.id, value="10-K")
    session.add(dv)

    session.commit()
    session.close()

    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as c:
        yield c

    engine.dispose()


def _assert_envelope(payload: Any) -> None:
    assert isinstance(payload, dict)
    assert set(payload.keys()) == {"ok", "data", "error", "meta"}

    assert isinstance(payload["ok"], bool)

    meta = payload["meta"]
    assert isinstance(meta, dict)
    assert "request_id" in meta

    # ok -> error must be null, fail -> error must be object
    if payload["ok"] is True:
        assert payload["error"] is None
    else:
        assert isinstance(payload["error"], dict)
        assert "code" in payload["error"]
        assert "message" in payload["error"]


def test_api_v1_jobs_json_envelope(client):
    res = client.get("/api/v1/admin/jobs")
    assert res.status_code == 200
    payload = res.get_json()
    _assert_envelope(payload)

    assert payload["ok"] is True
    data = payload["data"]
    assert isinstance(data, dict)
    assert "populate_daily_values" in data
    assert "recreate_sqlite_db" in data

    # Ensure job state has stable struct used by frontend
    for key in ("populate_daily_values", "recreate_sqlite_db"):
        state = data[key]
        assert isinstance(state, dict)
        for field in ("running", "started_at", "ended_at", "error"):
            assert field in state


@pytest.mark.parametrize(
    "path, expected_status",
    [
        ("/", 200),
        ("/check-cik", 200),
        ("/daily-values?entity_id=1", 200),
        ("/admin", 200),
        ("/db-check", 200),
    ],
)
def test_pages_render_html(client, path: str, expected_status: int):
    res = client.get(path)
    assert res.status_code == expected_status
    assert res.mimetype == "text/html"
