from __future__ import annotations

from pathlib import Path

import pytest

import db as db_module
from app import create_app
from api.services import daily_values_service as svc
from pytests.common import make_sqlite_engine, patch_app_db


@pytest.fixture()
def uninitialized_db_client(tmp_path, monkeypatch):
    """Flask test client backed by an *uninitialized* SQLite file.

    We create an engine for a brand new SQLite path but do NOT call
    Base.metadata.create_all(...). This simulates an empty DB file where tables
    don't exist yet.
    """

    db_path = tmp_path / "empty.sqlite"
    engine = make_sqlite_engine(Path(db_path))
    patch_app_db(monkeypatch, engine)

    app = create_app()
    return app.test_client(), engine


def test_service_handles_missing_tables(uninitialized_db_client):
    _client, engine = uninitialized_db_client

    session = db_module.SessionLocal()
    try:
        assert svc.count_entities_with_daily_values(session) == 0
        assert svc.list_entities_with_daily_values_page(session, offset=0, limit=20) == []
    finally:
        session.close()
        engine.dispose()


def test_check_cik_renders_empty_state_html(uninitialized_db_client):
    client, engine = uninitialized_db_client
    try:
        resp = client.get("/check-cik")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        body = resp.get_data(as_text=True)
        assert "No companies found yet" in body
    finally:
        engine.dispose()


def test_check_cik_empty_state_json(uninitialized_db_client):
    client, engine = uninitialized_db_client
    try:
        resp = client.get("/check-cik?format=json", headers={"Accept": "application/json"})
        assert resp.status_code == 200
        assert resp.mimetype == "application/json"
        payload = resp.get_json()

        assert payload["total"] == 0
        assert payload["count"] == 0
        assert payload["cards"] == []
        assert payload["has_more"] is False
    finally:
        engine.dispose()
