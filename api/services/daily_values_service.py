from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.daily_values import DailyValue
from models.dates import DateEntry
from models.entities import Entity
from models.entity_identifiers import EntityIdentifier
from models.units import Unit
from models.value_names import ValueName


def normalize_cik(cik: str) -> str:
    """Normalize CIK input.

    Behavior:
    - Trim whitespace
    - If numeric, interpret as an integer and left-pad to 10 digits (SEC common format)
      (this makes inputs like '1' and '0000000001' normalize to the same value)
    - Otherwise, return as-is (trimmed)
    """
    raw = (cik or "").strip()
    if raw.isdigit():
        return str(int(raw)).zfill(10)
    return raw


def list_entities_with_daily_values(session: Session) -> List[Entity]:
    """Return entities that have at least one DailyValue row."""
    return (
        session.query(Entity)
        .join(DailyValue, DailyValue.entity_id == Entity.id)
        .distinct()
        .order_by(func.coalesce(Entity.cik, ""), Entity.id)
        .all()
    )


def count_entities_with_daily_values(session: Session) -> int:
    """Return number of entities that have at least one DailyValue."""
    # COUNT(DISTINCT entities.id) with the join to restrict to entities with values.
    return int(
        session.query(func.count(func.distinct(Entity.id)))
        .join(DailyValue, DailyValue.entity_id == Entity.id)
        .scalar()
        or 0
    )


def list_entities_with_daily_values_page(
    session: Session, *, offset: int, limit: int
) -> List[Entity]:
    """Return a single page of entities that have at least one DailyValue."""
    if offset < 0:
        offset = 0
    # Safety bounds (avoid someone asking for 1M rows and killing the server).
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200

    return (
        session.query(Entity)
        .join(DailyValue, DailyValue.entity_id == Entity.id)
        .distinct()
        .order_by(func.coalesce(Entity.cik, ""), Entity.id)
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_entity_by_cik(session: Session, cik: str) -> Optional[Entity]:
    """Lookup entity by normalized CIK.

    Strict matching uses `entity_identifiers`.

    Compatibility: legacy code/tests may only populate `entities.cik`.
    In that case, fall back to matching on `Entity.cik` directly.
    """
    norm = normalize_cik(cik)
    if not norm:
        return None

    entity = (
        session.query(Entity)
        .join(EntityIdentifier, EntityIdentifier.entity_id == Entity.id)
        .filter(EntityIdentifier.scheme == "sec_cik")
        .filter(EntityIdentifier.value == norm)
        .first()
    )
    if entity is not None:
        return entity

    # Legacy fallback (non-strict) for older DBs/tests.
    return session.query(Entity).filter(Entity.cik == norm).first()


def get_daily_values_filter_options(
    session: Session, *, entity_id: int
) -> Tuple[List[str], List[str]]:
    """Return (value_name_options, unit_options) for a given entity."""
    value_name_options = [
        r[0]
        for r in (
            session.query(ValueName.name)
            .join(DailyValue, DailyValue.value_name_id == ValueName.id)
            .filter(DailyValue.entity_id == entity_id)
            .distinct()
            .order_by(ValueName.name)
            .all()
        )
    ]

    unit_options = [
        r[0]
        for r in (
            session.query(Unit.name)
            .join(ValueName, ValueName.unit_id == Unit.id)
            .join(DailyValue, DailyValue.value_name_id == ValueName.id)
            .filter(DailyValue.entity_id == entity_id)
            .distinct()
            .order_by(Unit.name)
            .all()
        )
    ]

    return value_name_options, unit_options


def build_daily_values_query(
    session: Session,
    *,
    entity_id: int,
    value_name_filters: Sequence[str],
    unit_filter: str,
    value_name_options: Sequence[str],
    unit_options: Sequence[str],
):
    """Build the daily values query and return (query, normalized_filters).

    Filters are normalized to match the prior route behavior:
    - value_name filters are ignored if not in available options
    - unit filter is ignored unless in available unit options
    """
    query = (
        session.query(DailyValue, DateEntry, ValueName, Unit)
        .join(DateEntry, DailyValue.date_id == DateEntry.id)
        .join(ValueName, DailyValue.value_name_id == ValueName.id)
        .outerjoin(Unit, ValueName.unit_id == Unit.id)
        .filter(DailyValue.entity_id == entity_id)
    )

    valid_value_name_filters = [
        vn for vn in value_name_filters if vn in value_name_options
    ]
    if valid_value_name_filters:
        query = query.filter(ValueName.name.in_(valid_value_name_filters))

    normalized_unit = unit_filter if unit_filter and unit_filter in unit_options else ""
    if normalized_unit:
        query = query.filter(Unit.name == normalized_unit)

    return query, valid_value_name_filters, normalized_unit


def serialize_daily_values_rows(
    *,
    entity: Entity,
    entity_id: int,
    rows: Sequence[Tuple[DailyValue, DateEntry, ValueName, Optional[Unit]]],
    parse_value,
) -> List[Dict[str, Any]]:
    """Serialize joined DailyValue rows for JSON output."""
    return [
        {
            "entity_id": entity_id,
            "cik": entity.cik,
            "date": str(dv_date.date),
            "value_name": vn.name,
            "unit": (unit.name if unit else "NA"),
            "value": parse_value(dv.value),
        }
        for dv, dv_date, vn, unit in rows
    ]
