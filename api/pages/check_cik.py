from flask import Blueprint, request, redirect, url_for, render_template, jsonify

import db
from models.daily_values import DailyValue
from models.entity_metadata import EntityMetadata

from api.services.daily_values_service import (
    get_entity_by_cik,
    list_entities_with_daily_values,
    normalize_cik,
)

check_cik_bp = Blueprint("check_cik", __name__)


def _serialize_entity_card(session, entity):
    meta_row = session.query(EntityMetadata).filter_by(entity_id=entity.id).first()
    metadata = {}
    company_name = None

    if meta_row is not None:
        company_name = getattr(meta_row, "company_name", None)
        for col in meta_row.__table__.columns:
            if col.name == "entity_id":
                continue
            metadata[col.name] = getattr(meta_row, col.name)

    # Provide a stable ordering for the most useful fields
    prefer_order = [
        "company_name",
        "sic",
        "sic_description",
        "state_of_incorporation",
        "fiscal_year_end",
        "filer_category",
        "entity_type",
        "tickers",
        "exchanges",
        "business_city",
        "business_state",
        "phone",
        "website",
        "ein",
    ]

    ordered_metadata = {}
    for k in prefer_order:
        if k in metadata:
            ordered_metadata[k] = metadata[k]
    for k in sorted(metadata.keys()):
        if k not in ordered_metadata:
            ordered_metadata[k] = metadata[k]

    return {
        "entity_id": entity.id,
        "cik": entity.cik,
        "company_name": company_name,
        "metadata": ordered_metadata,
    }


@check_cik_bp.route("/check-cik", methods=["GET"])
def check_cik_page():
    """CIK selection page.

    UX:
    - No dropdown. Instead show CIKs as selectable cards with metadata.
    - Preload 20 cards on initial HTML render.
    - A "Load more" button fetches additional cards via JSON from this same route.

    Behavior compatibility:
    - If a CIK is provided and it has data, redirect to /daily-values as before.
    """
    cik_input = request.args.get("cik", "").strip()
    cik = normalize_cik(cik_input)

    # Pagination for card list
    offset = request.args.get("offset", default=0, type=int)
    limit = request.args.get("limit", default=20, type=int)
    fmt = (request.args.get("format") or "").lower().strip()

    session = db.SessionLocal()
    try:
        entities = list_entities_with_daily_values(session)

        # If the user is selecting cards incrementally
        if fmt == "json" or request.accept_mimetypes.best == "application/json":
            slice_ = entities[offset : offset + limit]
            cards = [_serialize_entity_card(session, e) for e in slice_]
            next_offset = offset + len(cards)
            has_more = next_offset < len(entities)
            return jsonify(
                {
                    "offset": offset,
                    "limit": limit,
                    "count": len(cards),
                    "total": len(entities),
                    "next_offset": next_offset,
                    "has_more": has_more,
                    "cards": cards,
                }
            )

        message = ""
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

        # Initial HTML render: preload first 20
        preload_offset = 0
        preload_limit = 20
        preload_entities = entities[preload_offset : preload_offset + preload_limit]
        cards = [_serialize_entity_card(session, e) for e in preload_entities]
        next_offset = preload_offset + len(cards)
        has_more = next_offset < len(entities)

        return (
            render_template(
                "pages/check_cik.html",
                cards=cards,
                message=message,
                next_offset=next_offset,
                limit=preload_limit,
                has_more=has_more,
                total=len(entities),
            ),
            200,
        )
    finally:
        session.close()
