from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from models.dates import DateEntry
from models.daily_values_text import DailyValueText
from models.entities import Entity
from models.value_names import ValueName

from pytests.common import create_empty_sqlite_db


def test_daily_values_text_schema_and_insert_roundtrip(tmp_path):
    """Ensure `DailyValueText` stores non-numeric values and enforces uniqueness."""

    session, engine = create_empty_sqlite_db(tmp_path / "test.db")
    try:
        # Seed FK tables via ORM
        entity = Entity(cik="0000000001")
        date_entry = DateEntry(date=datetime.strptime("2026-01-01", "%Y-%m-%d").date())
        vn = ValueName(name="form", source=1, added_on=datetime.utcnow())
        session.add_all([entity, date_entry, vn])
        session.commit()

        dv = DailyValueText(
            entity_id=entity.id,
            date_id=date_entry.id,
            value_name_id=vn.id,
            value_text="10-K",
        )
        session.add(dv)
        session.commit()

        got = (
            session.query(DailyValueText)
            .filter_by(
                entity_id=entity.id,
                date_id=date_entry.id,
                value_name_id=vn.id,
            )
            .one()
        )
        assert got.value_text == "10-K"

        # Uniqueness constraint on (entity_id, date_id, value_name_id)
        session.add(
            DailyValueText(
                entity_id=entity.id,
                date_id=date_entry.id,
                value_name_id=vn.id,
                value_text="10-Q",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()
        engine.dispose()
