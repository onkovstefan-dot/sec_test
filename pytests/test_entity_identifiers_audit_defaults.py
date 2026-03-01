from __future__ import annotations

from utils.populate_daily_values import get_or_create_entity_by_identifier
from utils.time_utils import ensure_utc, utcnow


def test_new_entity_identifier_sets_audit_defaults(tmp_path, monkeypatch) -> None:
    # Use a temp DB via the existing test helper.
    from pytests.common import create_empty_sqlite_db

    session, engine = create_empty_sqlite_db(tmp_path / "t.sqlite")

    # Patch ingestion module globals so it uses our temp DB session.
    monkeypatch.setattr(
        "utils.populate_daily_values.session",
        session,
        raising=False,
    )
    monkeypatch.setattr(
        "utils.populate_daily_values.engine",
        engine,
        raising=False,
    )

    before = utcnow()
    ent = get_or_create_entity_by_identifier(
        scheme="sec_cik",
        value="0000320193",
        session=session,
        issuer="sec",
    )
    session.commit()

    ident = (
        session.query(
            __import__("models.entity_identifiers").entity_identifiers.EntityIdentifier
        )
        .filter_by(entity_id=ent.id, scheme="sec_cik")
        .first()
    )
    assert ident is not None

    # Audit columns should exist and be set.
    assert getattr(ident, "confidence") == "authoritative"
    assert getattr(ident, "added_at") is not None
    assert getattr(ident, "last_seen_at") is not None

    # SQLite can round-trip datetimes as naive; normalize before comparing.
    assert ensure_utc(ident.added_at) >= before
    assert ensure_utc(ident.last_seen_at) >= before
