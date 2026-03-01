from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from sqlalchemy.orm import Session as SASession

from db import Base, SessionLocal, engine
from logging_utils import get_logger
from models.entities import Entity
from models.entity_identifiers import EntityIdentifier
from models.sec_filings import SecFiling
from utils.sec_edgar_api import fetch_rss_feed

logger = get_logger(__name__)


_DEFAULT_ATOM_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&CIK=&type=&company=&dateb=&owner=include&start=0&count=40&output=atom"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Poll SEC EDGAR Atom feed and upsert pending sec_filings"
    )
    p.add_argument("--url", default=_DEFAULT_ATOM_URL, help="Atom feed URL")
    p.add_argument("--limit", type=int, default=50, help="Max entries to process")
    return p.parse_args(argv)


def _extract_cik(text: str) -> str | None:
    # Common patterns in SEC feeds: 'CIK=0000320193' or 'cik=0000320193'
    m = re.search(r"\bCIK=([0-9]{1,10})\b", text, flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(1).zfill(10)


def _extract_cik_from_link(link: str | None) -> str | None:
    """Extract CIK from a typical EDGAR archive link.

    Example:
      https://www.sec.gov/Archives/edgar/data/1824920/000119312526083754/...
    """

    if not link:
        return None
    try:
        path = urlparse(str(link)).path or ""
    except Exception:
        path = str(link)

    marker = "/Archives/edgar/data/"
    if marker not in path:
        return None
    tail = path.split(marker, 1)[1]
    parts = [p for p in tail.split("/") if p]
    if not parts:
        return None
    if parts[0].isdigit():
        return parts[0].zfill(10)
    return None


def _derive_edgar_urls(
    *, link: str | None, accession_number: str | None
) -> tuple[str | None, str | None, str | None]:
    """Best-effort derivation of index/document/full-text URLs from an Atom entry link.

    Returns (index_url, document_url, full_text_url).

    The SEC Atom feed link may be either an `*-index.htm` page or another file
    under `/Archives/edgar/data/{cik}/{acc_nodash}/...`.

    We aim to set `document_url` to the submission text (`{acc}.txt`) so that
    `sec_api_ingest.py` always has something fetchable without needing to parse
    the index page.
    """

    if not link:
        return (None, None, None)

    try:
        parsed = urlparse(str(link))
        path = parsed.path or ""
    except Exception:
        parsed = None
        path = str(link)

    acc = str(accession_number).strip().replace("-", "") if accession_number else ""
    if not acc:
        # Without accession we cannot construct the canonical .txt.
        return (str(link), None, None)

    marker = "/Archives/edgar/data/"
    if marker not in path:
        # Not an archives link; keep the link but don't guess more.
        return (str(link), None, None)

    # Canonical under the same directory as the feed link.
    base_dir = path.rsplit("/", 1)[0]  # /Archives/edgar/data/{cik}/{acc_nodash}

    full_text_path = f"{base_dir}/{acc}.txt"
    index_path = f"{base_dir}/{acc}-index.htm"

    def _abs(p: str) -> str:
        if parsed and parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}{p}"
        # Fall back to original string if parsing failed.
        return str(link)

    full_text_url = _abs(full_text_path)
    index_url = _abs(index_path)

    # `document_url` is what sec_api_ingest fetches; use the .txt.
    return (index_url, full_text_url, full_text_url)


def parse_atom_entries(atom_bytes: bytes) -> list[dict]:
    """Parse SEC Atom feed into a small normalized entry dict list.

    Returns list entries with keys:
      - cik (10-digit str) or None
      - accession_number (str or None)
      - form_type (str or None)
      - link (str or None)

    Notes:
      - This is a best-effort parser for tests and basic ingestion; fields may be missing.
    """

    root = ET.fromstring(atom_bytes)

    # Atom namespace handling: tolerate missing namespace by matching localname.
    def _iter_entries():
        for el in root.iter():
            if el.tag.endswith("entry"):
                yield el

    out: list[dict] = []
    for entry in _iter_entries():
        title = "".join(entry.findtext("{*}title") or "")
        summary = "".join(entry.findtext("{*}summary") or "")

        link = None
        for l in entry.findall("{*}link"):
            href = l.attrib.get("href")
            if href:
                link = href
                break

        text = " ".join([title, summary, link or ""]).strip()

        cik = _extract_cik(text) or _extract_cik_from_link(link)

        # Accessions sometimes appear as 0000320193-24-000001 in title.
        acc = None
        m_acc = re.search(r"\b([0-9]{10}-[0-9]{2}-[0-9]{6})\b", text)
        if m_acc:
            acc = m_acc.group(1).replace("-", "")

        # Form type often appears like '8-K' / '10-K' in title.
        form_type = None
        m_form = re.search(r"\b([0-9]{1,3}[A-Z\-]{0,5}|S-1|S-3|F-1|F-3)\b", title)
        if m_form:
            form_type = m_form.group(1)

        out.append(
            {
                "cik": cik,
                "accession_number": acc,
                "form_type": form_type,
                "link": link,
            }
        )

    return out


def run_poll(*, session: SASession, url: str, limit: int = 50) -> dict[str, int]:
    atom = fetch_rss_feed(url=url)
    entries = parse_atom_entries(atom)[: max(0, int(limit))]

    inserted = 0
    unknown = 0
    created_entities = 0

    for e in entries:
        cik = e.get("cik")
        acc = e.get("accession_number")
        form_type = e.get("form_type")
        link = e.get("link")

        if not cik:
            continue

        # Entity identifiers in this DB are stored as non-zero-padded digits.
        # Normalize to that format for lookup.
        cik_lookup = str(cik).zfill(10)

        # Derive URLs as best we can. This performs no external calls.
        index_url, document_url, full_text_url = _derive_edgar_urls(
            link=str(link) if link else None,
            accession_number=str(acc) if acc else None,
        )
        if acc and not document_url:
            logger.debug(
                "Could not derive document_url from feed link | cik=%s acc=%s link=%s",
                cik_lookup,
                acc,
                link,
            )

        ident = (
            session.query(EntityIdentifier)
            .filter_by(scheme="sec_cik", value=cik_lookup)
            .first()
        )
        if ident is None:
            unknown += 1
            continue

        if not acc or not form_type:
            continue

        existing = (
            session.query(SecFiling)
            .filter_by(entity_id=ident.entity_id, accession_number=str(acc))
            .first()
        )
        if existing is not None:
            continue

        session.add(
            SecFiling(
                entity_id=ident.entity_id,
                accession_number=str(acc),
                form_type=str(form_type),
                index_url=index_url,
                document_url=document_url,
                full_text_url=full_text_url,
                fetch_status="pending",
                source="sec_rss",
            )
        )
        inserted += 1

    session.commit()
    return {
        "inserted": inserted,
        "unknown_cik": unknown,
        "created_entities": 0,
        "entries": len(entries),
    }


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as s:
        summary = run_poll(session=s, url=str(args.url), limit=int(args.limit))

    logger.info(
        "sec_rss_poller complete | entries=%s inserted=%s unknown_cik=%s",
        summary["entries"],
        summary["inserted"],
        summary["unknown_cik"],
    )


if __name__ == "__main__":
    main()
