from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import or_
from sqlalchemy.orm import Session as SASession

from db import Base, SessionLocal, engine
from logging_utils import get_logger
from models.sec_filings import SecFiling
from utils.sec_edgar_api import SecEdgarApiError, fetch_filing_document
from utils.time_utils import utcnow

logger = get_logger(__name__)


RAW_DATA_DIR = Path(__file__).resolve().parents[1] / "raw_data"
FORMS_DIR = RAW_DATA_DIR / "forms"

# A curated, common set for quick interactive selection.
SUGGESTED_FORM_TYPES: list[str] = [
    "10-K",
    "10-Q",
    "8-K",
    "S-1",
    "DEF 14A",
    "13F-HR",
    "4",
]


@dataclass(frozen=True)
class IngestResult:
    filing_id: int
    ok: bool
    error: str | None = None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch pending SEC filings and store to raw_data/forms"
    )
    p.add_argument(
        "--form-types",
        default=None,
        help=(
            "Comma-separated list of SEC form types to include (e.g. '10-K,8-K'). "
            "If omitted, the script will offer an interactive selection menu."
        ),
    )
    p.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max number of filings to fetch this run (default: 50)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Concurrent download workers (threads) (default: 4)",
    )
    return p.parse_args(argv)


def _parse_csv_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [t.strip() for t in str(value).split(",")]
    items = [t for t in items if t]
    return items or None


def _prompt_form_types_interactive() -> list[str] | None:
    """Prompt for `form_types` when user didn't pass `--form-types`.

    Returns:
      - list[str] for a chosen subset
      - None to include all form types
    """

    print("\nSelect SEC form types to ingest:")
    print("  0) All form types (no filter)")
    for i, ft in enumerate(SUGGESTED_FORM_TYPES, start=1):
        print(f"  {i}) {ft}")
    print("\nEnter one or more numbers (comma-separated). Examples: 1 or 1,3,4")
    print("Or type a custom comma-separated list (e.g. 10-K,8-K).")
    raw = input("Selection [0]: ").strip()

    if raw == "" or raw == "0":
        return None

    # If it's purely numeric selections, map them.
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if parts and all(p.isdigit() for p in parts):
        selected: list[str] = []
        for p in parts:
            n = int(p)
            if n == 0:
                return None
            idx = n - 1
            if idx < 0 or idx >= len(SUGGESTED_FORM_TYPES):
                raise SystemExit(f"Invalid selection: {n}")
            selected.append(SUGGESTED_FORM_TYPES[idx])
        # de-dupe while preserving order
        out: list[str] = []
        seen: set[str] = set()
        for t in selected:
            if t not in seen:
                out.append(t)
                seen.add(t)
        return out or None

    # Otherwise treat input as a normal CSV list of form types.
    return _parse_csv_list(raw)


def _normalize_accession(accession: str) -> str:
    return str(accession).strip().replace("-", "")


def _safe_dirname(s: str) -> str:
    # accession and cik are digits; keep this defensive anyway.
    return "".join(ch for ch in str(s) if ch.isalnum() or ch in {"-", "_"})


def _filing_dir(*, cik: str, accession_number: str) -> Path:
    return (
        FORMS_DIR
        / _safe_dirname(str(cik))
        / _safe_dirname(_normalize_accession(accession_number))
    )


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _infer_cik_from_filing(filing: SecFiling) -> str | None:
    """Infer CIK from any stored SEC archive URL.

    Typical URL form:
      https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/...
    """

    for url in (filing.document_url, filing.index_url, filing.full_text_url):
        if not url:
            continue
        s = str(url)
        marker = "/Archives/edgar/data/"
        if marker not in s:
            continue
        tail = s.split(marker, 1)[1]
        parts = tail.split("/")
        if parts and parts[0].isdigit():
            return parts[0]
    return None


def _fetch_and_save_one(*, filing: SecFiling) -> IngestResult:
    if not filing.document_url:
        return IngestResult(filing_id=filing.id, ok=False, error="missing_document_url")

    cik = _infer_cik_from_filing(filing)
    if not cik:
        return IngestResult(filing_id=filing.id, ok=False, error="cannot_infer_cik")

    doc_name = os.path.basename(str(filing.document_url))
    if not doc_name:
        return IngestResult(
            filing_id=filing.id, ok=False, error="cannot_infer_document_name"
        )

    try:
        content = fetch_filing_document(
            cik=str(cik),
            accession_number=filing.accession_number,
            document_name=doc_name,
        )

        out_dir = _filing_dir(cik=str(cik), accession_number=filing.accession_number)
        _write_bytes(out_dir / doc_name, content)

        return IngestResult(filing_id=filing.id, ok=True)
    except SecEdgarApiError as e:
        return IngestResult(filing_id=filing.id, ok=False, error=str(e))
    except Exception as e:  # pragma: no cover
        return IngestResult(
            filing_id=filing.id, ok=False, error=f"{type(e).__name__}: {e}"
        )


def run_ingest(
    *,
    session: SASession,
    form_types: list[str] | None,
    limit: int,
    workers: int,
) -> dict[str, int]:
    """Run one ingest pass.

    Updates `sec_filings.fetch_status` and `sec_filings.fetched_at`.

    Returns summary counts.
    """

    q = session.query(SecFiling).filter(
        or_(
            SecFiling.fetch_status == None, SecFiling.fetch_status == "pending"
        )  # noqa: E711
    )
    if form_types:
        q = q.filter(SecFiling.form_type.in_(form_types))

    filings = q.order_by(SecFiling.id.asc()).limit(limit).all()

    if not filings:
        return {"selected": 0, "fetched": 0, "failed": 0}

    fetched = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as ex:
        futs = [ex.submit(_fetch_and_save_one, filing=f) for f in filings]

        for fut in as_completed(futs):
            res = fut.result()
            filing = session.query(SecFiling).filter_by(id=res.filing_id).first()
            if filing is None:
                continue

            if res.ok:
                filing.fetch_status = "fetched"
                filing.fetched_at = utcnow()
                fetched += 1
            else:
                filing.fetch_status = "failed"
                failed += 1

    session.commit()
    return {"selected": len(filings), "fetched": fetched, "failed": failed}


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    # Use CLI arg when provided; otherwise offer a simple interactive choice.
    form_types: list[str] | None = _parse_csv_list(args.form_types)
    if form_types is None and not args.form_types:
        try:
            form_types = _prompt_form_types_interactive()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit("Aborted.")

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as s:
        summary = run_ingest(
            session=s,
            form_types=form_types,
            limit=int(args.limit),
            workers=int(args.workers),
        )

    logger.info(
        "sec_api_ingest complete | selected=%s fetched=%s failed=%s",
        summary["selected"],
        summary["fetched"],
        summary["failed"],
    )


if __name__ == "__main__":
    main()
