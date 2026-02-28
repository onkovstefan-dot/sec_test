from flask import Blueprint, jsonify, request, render_template

from db import SessionLocal
from models.entities import Entity
from utils.value_parsing import parse_primitive

from api.services.daily_values_service import (
    build_daily_values_query,
    get_daily_values_filter_options,
    serialize_daily_values_rows,
)


daily_values_bp = Blueprint("daily_values", __name__)


@daily_values_bp.route("/daily-values", methods=["GET"])
def daily_values_page():
    """Second page: display daily_values for a given entity_id (required)."""
    entity_id = request.args.get("entity_id", type=int)

    # Optional filters
    value_name_filters = [
        v.strip() for v in request.args.getlist("value_name") if v and v.strip()
    ]
    unit_filter = (request.args.get("unit") or "").strip()

    session = SessionLocal()
    try:
        if not entity_id:
            return (
                "Missing required query param: entity_id",
                400,
                {"Content-Type": "text/plain"},
            )

        entity = session.query(Entity).filter(Entity.id == entity_id).first()
        if not entity:
            return (
                f"No entity found for entity_id={entity_id}",
                404,
                {"Content-Type": "text/plain"},
            )

        value_name_options, unit_options = get_daily_values_filter_options(
            session, entity_id=entity_id
        )

        query, value_name_filters, unit_filter = build_daily_values_query(
            session,
            entity_id=entity_id,
            value_name_filters=value_name_filters,
            unit_filter=unit_filter,
            value_name_options=value_name_options,
            unit_options=unit_options,
        )

        # ordering matches prior behavior
        from models.dates import DateEntry
        from models.value_names import ValueName

        rows = query.order_by(DateEntry.date, ValueName.name).all()

        serialized_rows = serialize_daily_values_rows(
            entity=entity,
            entity_id=entity_id,
            rows=rows,
            parse_value=parse_primitive,
        )

        # JSON response (kept for API use)
        if request.accept_mimetypes.best == "application/json":
            return jsonify(
                {
                    "entity_id": entity_id,
                    "cik": entity.cik,
                    "count": len(serialized_rows),
                    "rows": serialized_rows,
                }
            )

        return (
            render_template(
                "pages/daily_values.html",
                entity=entity,
                entity_id=entity_id,
                rows=serialized_rows,
                value_name_options=value_name_options,
                unit_options=unit_options,
                value_name_filters=value_name_filters,
                unit_filter=unit_filter,
            ),
            200,
        )
    finally:
        session.close()
