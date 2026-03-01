from __future__ import annotations

from flask import Blueprint, render_template, request


filings_search_bp = Blueprint("filings_search", __name__)


@filings_search_bp.route("/filings/search", methods=["GET"])
def filings_search_page():
    """Minimal UI for filings keyword search (calls /api/v1/filings/search)."""

    # Pre-fill from querystring.
    q = (request.args.get("q") or "").strip()
    form_type = (request.args.get("form_type") or "").strip()
    cik = (request.args.get("cik") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()

    return (
        render_template(
            "pages/filings_search.html",
            q=q,
            form_type=form_type,
            cik=cik,
            date_from=date_from,
            date_to=date_to,
        ),
        200,
    )
