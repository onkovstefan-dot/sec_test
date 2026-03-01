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


def test_admin_routes_removed(client):
    assert client.get("/admin").status_code == 404
    assert client.get("/admin/").status_code == 404
    assert client.post("/admin/recreate-db").status_code == 404
