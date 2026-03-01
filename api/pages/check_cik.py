from flask import Blueprint, request, redirect, url_for, render_template

import db
from models.daily_values import DailyValue
from models.entity_metadata import EntityMetadata

from api.services.daily_values_service import (
    get_entity_by_cik,
    list_entities_with_daily_values,
    normalize_cik,
)

check_cik_bp = Blueprint("check_cik", __name__)


@check_cik_bp.route("/check-cik", methods=["GET"])
def check_cik_page():
    """CIK selection page: if data exists redirect to /daily-values, else show message."""
    cik_input = request.args.get("cik", "").strip()
    cik = normalize_cik(cik_input)

    session = db.SessionLocal()
    try:
        # Only show entities that actually have at least one daily_values row
        entities = list_entities_with_daily_values(session)

        message = ""
        selected_metadata = None
        if cik:
            selected_entity = get_entity_by_cik(session, cik)

            # Fallback: match by integer value in case stored CIKs have legacy formatting
            if not selected_entity and cik_input.strip().isdigit():
                try:
                    target = int(cik_input.strip())
                    selected_entity = next(
                        (e for e in entities if int(e.cik) == target), None
                    )
                except Exception:
                    selected_entity = None

            if not selected_entity:
                message = f"No entity found for CIK '{cik}'."
            else:
                meta_row = (
                    session.query(EntityMetadata)
                    .filter_by(entity_id=selected_entity.id)
                    .first()
                )
                if meta_row is not None:
                    selected_metadata = {
                        col.name: getattr(meta_row, col.name)
                        for col in meta_row.__table__.columns
                        if getattr(meta_row, col.name) is not None
                        and col.name != "entity_id"
                    }

                has_data = (
                    session.query(DailyValue.id)
                    .filter(DailyValue.entity_id == selected_entity.id)
                    .limit(1)
                    .first()
                    is not None
                )
                if has_data:
                    return redirect(
                        url_for(
                            "api.daily_values.daily_values_page",
                            entity_id=selected_entity.id,
                        )
                    )
                message = f"No daily values found for CIK '{cik}'."

        return (
            render_template(
                "pages/check_cik.html",
                entities=entities,
                cik=cik,
                message=message,
                selected_metadata=selected_metadata,
            ),
            200,
        )
    finally:
        session.close()
