from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlencode

import requests


@dataclass(frozen=True)
class EftsFilingHit:
    accession_number: str | None
    cik: str | None
    form_type: str | None
    filed_at: str | None
    company_name: str | None
    link: str | None
    snippet: str | None


def _build_efts_search_url(
    *,
    q: str,
    form_type: str | None = None,
    cik: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> str:
    """Build an EFTS search URL.

    Notes:
    - EFTS public endpoint is not formally documented as an API; keep best-effort.
    - Parameters are intentionally conservative; server-side behavior may change.
    """

    base = "https://efts.sec.gov/LATEST/search-index"

    # EFTS uses query-string args; keep names stable and explicit.
    params: dict[str, Any] = {
        "q": q,
        "limit": int(limit),
        "offset": 0,
    }
    if form_type:
        params["forms"] = form_type
    if cik:
        params["ciks"] = cik
    if date_from:
        params["from"] = date_from
    if date_to:
        params["to"] = date_to

    return f"{base}?{urlencode(params)}"


def fetch_efts_search(
    *,
    q: str,
    form_type: str | None = None,
    cik: str | None = None,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
    limit: int = 20,
    session: requests.Session | None = None,
    timeout_s: float = 30.0,
) -> list[EftsFilingHit]:
    """Search SEC EFTS for filings containing keyword(s).

    Returns a best-effort normalized list of hits.

    Caller is responsible for SEC-compliant User-Agent if required. EFTS may not
    enforce it the same way as EDGAR Archives, but keep usage consistent.
    """

    if not q or not q.strip():
        return []

    if isinstance(date_from, date):
        date_from = date_from.isoformat()
    if isinstance(date_to, date):
        date_to = date_to.isoformat()

    limit = max(1, min(int(limit), 200))

    url = _build_efts_search_url(
        q=q.strip(),
        form_type=form_type,
        cik=cik,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

    sess = session or requests.Session()
    resp = sess.get(url, timeout=timeout_s)
    resp.raise_for_status()

    # EFTS sometimes returns JSON with wrong content-type; parse defensively.
    payload: Any
    try:
        payload = resp.json()
    except Exception:
        payload = json.loads(resp.text)

    return parse_efts_response(payload)


def parse_efts_response(payload: Any) -> list[EftsFilingHit]:
    """Parse an EFTS response into normalized hits.

    The format is not guaranteed stable; parse defensively.
    """

    hits_out: list[EftsFilingHit] = []

    if not isinstance(payload, dict):
        return hits_out

    # Observed structure (best-effort): {"hits": {"hits": [{"_source": {...}}]}}
    hits = payload.get("hits")
    if isinstance(hits, dict):
        inner = hits.get("hits")
        if isinstance(inner, list):
            for item in inner:
                if not isinstance(item, dict):
                    continue
                src = item.get("_source")
                if not isinstance(src, dict):
                    src = {}

                # Field names vary across indices; map common candidates.
                accession = src.get("adsh") or src.get("accessionNumber")
                cik = src.get("cik")
                form = src.get("form") or src.get("formType")
                filed_at = src.get("filedAt") or src.get("filed")
                company = src.get("companyName") or src.get("company")
                link = src.get("link") or src.get("url")

                # Provide snippet if present (highlight is separate sometimes).
                snippet = None
                hl = item.get("highlight")
                if isinstance(hl, dict):
                    # Flatten first highlight list element if present.
                    for v in hl.values():
                        if isinstance(v, list) and v:
                            snippet = str(v[0])
                            break

                hits_out.append(
                    EftsFilingHit(
                        accession_number=(
                            str(accession) if accession is not None else None
                        ),
                        cik=str(cik) if cik is not None else None,
                        form_type=str(form) if form is not None else None,
                        filed_at=str(filed_at) if filed_at is not None else None,
                        company_name=str(company) if company is not None else None,
                        link=str(link) if link is not None else None,
                        snippet=str(snippet) if snippet is not None else None,
                    )
                )

    return hits_out
