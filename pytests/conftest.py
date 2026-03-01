from __future__ import annotations

import os
import socket
import threading
import time
from dataclasses import dataclass
from typing import Generator

import pytest
from werkzeug.serving import make_server

from app import create_app
from models.daily_values import DailyValue
from models.dates import DateEntry
from models.entities import Entity
from models.units import Unit
from models.value_names import ValueName
from pytests.common import create_empty_sqlite_db, patch_app_db


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@dataclass(frozen=True)
class LiveServer:
    base_url: str


@pytest.fixture(scope="session")
def browser_context_args():
    """Playwright pytest plugin hook.

    Ensures a deterministic viewport for screenshot/debugging and keeps tests stable.
    """

    return {
        "viewport": {"width": 1280, "height": 720},
    }


@pytest.fixture()
def seeded_live_server(tmp_path, monkeypatch) -> Generator[LiveServer, None, None]:
    """Start a real HTTP server (thread) backed by a temp SQLite DB.

    These tests are true E2E (browser -> HTTP -> Flask -> SQLite).

    Note: We explicitly disable INIT_DB_ON_STARTUP and use a temp DB to keep tests
    hermetic and avoid touching data/sec.db.
    """

    # Ensure app doesn't try to init real DB via env flag.
    monkeypatch.setenv("INIT_DB_ON_STARTUP", "0")

    session, engine = create_empty_sqlite_db(tmp_path / "e2e.sqlite")
    patch_app_db(monkeypatch, engine)

    # Seed: 2 entities, each with at least 1 daily value so /check-cik has cards.
    e1 = Entity(cik="0000000001")
    e2 = Entity(cik="0000000002")
    session.add_all([e1, e2])
    session.flush()

    import datetime as dt

    d = DateEntry(date=dt.date(2020, 1, 1))
    u = Unit(name="USD")
    vn = ValueName(name="Assets")
    session.add_all([d, u, vn])
    session.flush()

    # Some schemas have ValueName.unit_id; set only if present.
    if hasattr(ValueName, "unit_id"):
        vn.unit_id = u.id
        session.flush()

    def _dv_kwargs(entity_id: int, value: int):
        kwargs = {
            "entity_id": entity_id,
            "date_id": d.id,
            "value_name_id": vn.id,
            "value": value,
        }
        if hasattr(DailyValue, "unit_id"):
            kwargs["unit_id"] = u.id
        return kwargs

    session.add_all(
        [
            DailyValue(**_dv_kwargs(e1.id, 123)),
            DailyValue(**_dv_kwargs(e2.id, 456)),
        ]
    )
    session.commit()
    session.close()

    app = create_app()
    app.config.update(TESTING=True)

    port = _pick_free_port()
    server = make_server("127.0.0.1", port, app)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Small wait to ensure the socket is accepting.
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)

    try:
        yield LiveServer(base_url=f"http://127.0.0.1:{port}")
    finally:
        server.shutdown()
        thread.join(timeout=5)
        engine.dispose()
