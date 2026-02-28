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


def test_api_v1_admin_jobs_envelope_and_payload(client):
    resp = client.get("/api/v1/admin/jobs")
    assert resp.status_code == 200

    body = resp.get_json()
    assert set(body.keys()) == {"ok", "data", "error", "meta"}
    assert body["ok"] is True
    assert body["error"] in (None, "")

    data = body["data"]
    assert set(data.keys()) == {"populate_daily_values", "recreate_sqlite_db"}

    for job_name in ("populate_daily_values", "recreate_sqlite_db"):
        state = data[job_name]
        assert set(state.keys()) >= {"running", "started_at", "ended_at", "error"}
        assert isinstance(state["running"], bool)
