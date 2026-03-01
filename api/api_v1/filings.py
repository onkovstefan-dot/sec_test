from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import and_, or_

import db
from models.sec_filings import SecFiling
from utils.sec_efts_client import fetch_efts_search


filings_v1_bp = Blueprint("filings_v1", __name__)


def _iso_date_param(name: str) -> str | None:
    raw = (request.args.get(name) or "").strip()
    if not raw:
        return None
    # Expect YYYY-MM-DD. Keep simple; errors handled by caller.
    return raw


@filings_v1_bp.route("/filings/search", methods=["GET"])
def filings_search():
    """Search filings.

    Behavior:
    - Prefer local sec_filings records.
    - If no local hits and q is provided, fallback to SEC EFTS.

    Query params:
    - q: keyword(s), optional (required for EFTS fallback)
    - form_type: optional
    - cik: optional (best-effort; local search matches in URLs)
    - date_from/date_to: optional YYYY-MM-DD (local search uses filing_date)
    - limit: optional (default 20, max 200)
    """

    q = (request.args.get("q") or "").strip()
    form_type = (request.args.get("form_type") or "").strip() or None
    cik = (request.args.get("cik") or "").strip() or None

    date_from = _iso_date_param("date_from")
    date_to = _iso_date_param("date_to")

    try:
        limit = int((request.args.get("limit") or "").strip() or 20)
    except ValueError:
        limit = 20
    limit = max(1, min(limit, 200))

    session = db.SessionLocal()
    try:
        qry = session.query(SecFiling)

        filters = []
        if form_type:
            filters.append(SecFiling.form_type == form_type)

        # Local DB does not store CIK explicitly on filings; best-effort filter by URL.
        if cik:
            # Look for /data/{cik}/ in any URL columns.
            needle = f"/data/{int(cik)}/" if cik.isdigit() else f"/data/{cik}/"
            filters.append(
                or_(
                    SecFiling.index_url.like(f"%{needle}%"),
                    SecFiling.document_url.like(f"%{needle}%"),
                    SecFiling.full_text_url.like(f"%{needle}%"),
                )
            )

        if date_from:
            filters.append(SecFiling.filing_date >= date.fromisoformat(date_from))
        if date_to:
            filters.append(SecFiling.filing_date <= date.fromisoformat(date_to))

        if filters:
            qry = qry.filter(and_(*filters))

        local_rows = (
            qry.order_by(SecFiling.filing_date.desc().nullslast()).limit(limit).all()
        )

        if local_rows:
            return (
                jsonify(
                    {
                        "source": "local",
                        "count": len(local_rows),
                        "results": [
                            {
                                "id": r.id,
                                "entity_id": r.entity_id,
                                "accession_number": r.accession_number,
                                "form_type": r.form_type,
                                "filing_date": (
                                    r.filing_date.isoformat() if r.filing_date else None
                                ),
                                "report_date": (
                                    r.report_date.isoformat() if r.report_date else None
                                ),
                                "primary_document": r.primary_document,
                                "index_url": r.index_url,
                                "document_url": r.document_url,
                                "full_text_url": r.full_text_url,
                                "fetch_status": r.fetch_status,
                                "fetched_at": (
                                    r.fetched_at.isoformat() if r.fetched_at else None
                                ),
                                "source": r.source,
                            }
                            for r in local_rows
                        ],
                    }
                ),
                200,
            )

        # Fallback to EFTS.
        if not q:
            return (
                jsonify(
                    {
                        "source": "local",
                        "count": 0,
                        "results": [],
                    }
                ),
                200,
            )

        hits = fetch_efts_search(
            q=q,
            form_type=form_type,
            cik=cik,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

        return (
            jsonify(
                {
                    "source": "efts",
                    "count": len(hits),
                    "results": [
                        {
                            "accession_number": h.accession_number,
                            "cik": h.cik,
                            "form_type": h.form_type,
                            "filed_at": h.filed_at,
                            "company_name": h.company_name,
                            "link": h.link,
                            "snippet": h.snippet,
                        }
                        for h in hits
                    ],
                }
            ),
            200,
        )

    finally:
        session.close()
