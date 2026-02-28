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


def test_admin_page_renders(client):
    resp = client.get("/admin")
    # App may redirect /admin -> /admin/ depending on strict slashes.
    assert resp.status_code in (200, 301, 302)

    if resp.status_code in (301, 302):
        resp = client.get(resp.headers["Location"])

    assert resp.status_code == 200
    assert resp.content_type.startswith("text/html")


def test_admin_recreate_requires_confirmation(client):
    resp = client.post("/admin/recreate-db", data={"confirm": "nope"})
    assert resp.status_code in (301, 302)
    assert "/admin" in resp.headers.get("Location", "")
