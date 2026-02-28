from flask import Blueprint, request, redirect, url_for, render_template

from db import SessionLocal
from models.daily_values import DailyValue

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

    session = SessionLocal()
    try:
        # Only show entities that actually have at least one daily_values row
        entities = list_entities_with_daily_values(session)

        message = ""
        if cik:
            selected_entity = get_entity_by_cik(session, cik)
            if not selected_entity:
                message = f"No entity found for CIK '{cik}'."
            else:
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
            ),
            200,
        )
    finally:
        session.close()
