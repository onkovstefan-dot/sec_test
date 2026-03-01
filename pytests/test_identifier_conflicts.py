from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from utils.populate_daily_values import get_or_create_entity_by_identifier


def test_get_or_create_entity_by_identifier_raises_on_conflict(tmp_path) -> None:
    # Use a hermetic temp DB.
    from pytests.common import create_empty_sqlite_db

    session, engine = create_empty_sqlite_db(tmp_path / "conflict.sqlite")
    try:
        e1 = get_or_create_entity_by_identifier(
            scheme="sec_cik",
            value="0000320193",
            session=session,
            issuer="sec",
        )
        session.commit()

        # Second call attempts to claim same (scheme,value) from a different entity.
        # We do this by creating a new entity using a different identifier, then
        # explicitly attaching the conflicting identifier.
        e2 = get_or_create_entity_by_identifier(
            scheme="gleif_lei",
            value="5493001KJTIIGC8Y1R12",
            session=session,
            issuer="gleif",
        )
        session.commit()

        m = __import__("utils.populate_daily_values").populate_daily_values

        with pytest.raises(
            IntegrityError, match=r"Identifier conflict: sec_cik:0000320193"
        ):
            m._get_or_create_entity_identifier(
                session,
                entity_id=e2.id,
                scheme="sec_cik",
                value="0000320193",
                issuer="sec",
            )

    finally:
        session.close()
        engine.dispose()
