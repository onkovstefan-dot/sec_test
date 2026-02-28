from __future__ import annotations

import pytest

from app import create_app
from pytests.common import create_empty_sqlite_db, patch_app_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    _session, engine = create_empty_sqlite_db(tmp_path / "test.sqlite")
    patch_app_db(monkeypatch, engine)

    app = create_app()
    return app.test_client()


def test_db_check_renders_html(client):
    resp = client.get("/db-check")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/html")


def test_db_check_json_schema(client):
    resp = client.get("/db-check", headers={"Accept": "application/json"})
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/json")

    data = resp.get_json()
    assert set(data.keys()) == {
        "tables",
        "selected_table",
        "limit",
        "columns",
        "rows",
        "error",
    }
    assert isinstance(data["tables"], list)
    assert isinstance(data["selected_table"], str)
    assert isinstance(data["limit"], int)
    assert isinstance(data["columns"], list)
    assert isinstance(data["rows"], list)
    assert isinstance(data["error"], str)
