from __future__ import annotations

import argparse
import os
import sys
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

# Allow running this file directly (e.g. `python jobs/sec_api_ingest.py`) by
# ensuring the project root is importable.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import logging_utils

from sqlalchemy import or_
from sqlalchemy import func
from sqlalchemy.orm import Session as SASession

from db import Base, SessionLocal, engine
from logging_utils import get_logger
from models.sec_filings import SecFiling
from utils.sec_edgar_api import SecEdgarApiError, fetch_filing_document
from utils.time_utils import utcnow

logger = get_logger(__name__)

# Env vars that commonly affect this job and its integrations.
# Do not log values for secrets; only log whether set.
_DIAG_ENV_VARS: tuple[str, ...] = (
    "LOG_LEVEL",
    "SEC_TEST_LOG_DIR",
    "DATABASE_URL",
    "SQLALCHEMY_DATABASE_URL",
    "SEC_EDGAR_USER_AGENT",
    "SEC_API_KEY",
)

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


def _log_paths_hint() -> str:
    """Best-effort help message pointing to where logs are written."""

    # logging_utils writes per-module logs under ./logs by default.
    logs_dir = os.getenv("SEC_TEST_LOG_DIR")
    if logs_dir and logs_dir.strip():
        base = Path(logs_dir.strip())
        if not base.is_absolute():
            base = _PROJECT_ROOT / logs_dir.strip()
    else:
        base = _PROJECT_ROOT / "logs"

    # Note: actual filename may get a _1/_2 suffix if a file already exists.
    return f"logs_dir={base} (see also {base}/app.log and module log sec_test_jobs_sec_api_ingest*.log)"


def _env_presence_summary() -> str:
    parts: list[str] = []
    for k in _DIAG_ENV_VARS:
        v = os.getenv(k)
        if v is None:
            parts.append(f"{k}=<unset>")
        else:
            # For anything that might be sensitive, only log a boolean.
            if (
                "KEY" in k
                or "TOKEN" in k
                or "SECRET" in k
                or k in {"SEC_EDGAR_USER_AGENT"}
            ):
                parts.append(f"{k}=<set>")
            else:
                parts.append(f"{k}={v}")
    return ", ".join(parts)


def _startup_diagnostics() -> None:
    """Emit a one-shot diagnostic line to help debug 'failed to start'."""

    # Avoid spilling full env; just a curated list.
    logger.info(
        "Diagnostics | python=%s platform=%s cwd=%s project_root=%s raw_data=%s forms_dir=%s env={%s}",
        sys.version.split("\n", 1)[0],
        platform.platform(),
        os.getcwd(),
        _PROJECT_ROOT,
        RAW_DATA_DIR,
        FORMS_DIR,
        _env_presence_summary(),
    )

    try:
        # Log only the dialect/driver-ish prefix, not credentials.
        url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URL")
        if url:
            safe = url
            if "://" in safe:
                safe = safe.split("://", 1)[0] + "://<redacted>"
            logger.info("Diagnostics | database_url=%s", safe)
        else:
            # Often this project uses SQLite via db.py; still emit the engine URL.
            engine_url = getattr(
                getattr(engine, "url", None), "__str__", lambda: None
            )()
            if engine_url:
                logger.info("Diagnostics | engine.url=%s", str(engine.url))
    except Exception:
        logger.debug("Diagnostics | could not determine database url", exc_info=True)

    try:
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        FORMS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Diagnostics | ensured output dirs exist")
    except Exception:
        logger.exception("Diagnostics | cannot create output directories")


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
        "--log-level",
        default=None,
        help="Override LOG_LEVEL for this run (e.g. DEBUG, INFO, WARNING)",
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
        default=int(os.getenv("SEC_INGEST_DEFAULT_LIMIT", "10")),
        help=(
            "Max number of filings to fetch this run. "
            "Default is controlled by SEC_INGEST_DEFAULT_LIMIT (default: 10)."
        ),
    )
    p.add_argument(
        "--workers",
        type=int,
        default=int(os.getenv("SEC_INGEST_DEFAULT_WORKERS", "1")),
        help=(
            "Concurrent download workers (threads). "
            "Default is controlled by SEC_INGEST_DEFAULT_WORKERS (default: 1)."
        ),
    )
    p.add_argument(
        "--retry-failed",
        action="store_true",
        help=(
            "If set and no pending filings are selected, re-queue a small number of "
            "previously failed filings by setting fetch_status back to 'pending' before selecting. "
            "This is rate-limit friendly when combined with a low --limit."
        ),
    )
    # Use parse_known_args so VS Code / other launchers that inject extra args
    # won't break parsing or accidentally get captured as form types.
    args, unknown = p.parse_known_args(argv)
    if unknown:
        logger.debug("Ignoring unknown CLI args: %s", unknown)
    return args


def _parse_csv_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [t.strip() for t in str(value).split(",")]
    items = [t for t in items if t]
    return items or None


def _argv_for_debug(argv: list[str] | None) -> list[str]:
    # Helpful when run from VS Code play button / debugger.
    return list(sys.argv[1:] if argv is None else argv)


def _available_pending_form_types(
    *, session: SASession, limit_to: list[str] | None = None
) -> list[str]:
    """Return form types that currently have pending filings."""

    q = (
        session.query(SecFiling.form_type)
        .filter(
            or_(
                SecFiling.fetch_status == None, SecFiling.fetch_status == "pending"
            )  # noqa: E711
        )
        .filter(SecFiling.form_type != None)  # noqa: E711
    )

    if limit_to:
        q = q.filter(SecFiling.form_type.in_(limit_to))

    rows = q.distinct().order_by(func.lower(SecFiling.form_type).asc()).all()
    return [r[0] for r in rows if r and r[0]]


def _prompt_form_types_interactive_with_availability(
    *, session: SASession
) -> list[str] | None:
    """Interactive prompt that only shows currently-available pending form types."""

    available = _available_pending_form_types(
        session=session, limit_to=SUGGESTED_FORM_TYPES
    )

    if not available:
        print("\nNo pending filings found in the database.")
        print("Nothing to ingest right now.")
        return None

    print(
        "\nSelect SEC form types to ingest (only showing those with pending filings):"
    )
    print("  0) All available pending form types")
    for i, ft in enumerate(available, start=1):
        print(f"  {i}) {ft}")
    print("\nEnter one or more numbers (comma-separated). Examples: 1 or 1,3,4")
    print("Or type a custom comma-separated list (e.g. 10-K,8-K).")
    raw = input("Selection [0]: ").strip()

    if raw == "" or raw == "0":
        return None

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if parts and all(p.isdigit() for p in parts):
        selected: list[str] = []
        for p in parts:
            n = int(p)
            if n == 0:
                return None
            idx = n - 1
            if idx < 0 or idx >= len(available):
                raise SystemExit(f"Invalid selection: {n}")
            selected.append(available[idx])
        # de-dupe while preserving order
        out: list[str] = []
        seen: set[str] = set()
        for t in selected:
            if t not in seen:
                out.append(t)
                seen.add(t)
        return out or None

    return _parse_csv_list(raw)


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
        logger.warning(
            "Skipping filing: missing document_url | filing_id=%s accession=%s form_type=%s",
            getattr(filing, "id", None),
            getattr(filing, "accession_number", None),
            getattr(filing, "form_type", None),
        )
        return IngestResult(filing_id=filing.id, ok=False, error="missing_document_url")

    cik = _infer_cik_from_filing(filing)
    if not cik:
        logger.warning(
            "Skipping filing: cannot infer CIK | filing_id=%s accession=%s form_type=%s url=%s",
            getattr(filing, "id", None),
            getattr(filing, "accession_number", None),
            getattr(filing, "form_type", None),
            getattr(filing, "document_url", None),
        )
        return IngestResult(filing_id=filing.id, ok=False, error="cannot_infer_cik")

    doc_name = os.path.basename(str(filing.document_url))
    if not doc_name:
        logger.warning(
            "Skipping filing: cannot infer document name | filing_id=%s accession=%s form_type=%s url=%s",
            getattr(filing, "id", None),
            getattr(filing, "accession_number", None),
            getattr(filing, "form_type", None),
            getattr(filing, "document_url", None),
        )
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
        # Lower-level client logs status/body_preview; here we add filing context.
        logger.warning(
            "SEC download failed | filing_id=%s cik=%s accession=%s doc=%s form_type=%s err=%s",
            getattr(filing, "id", None),
            cik,
            getattr(filing, "accession_number", None),
            doc_name,
            getattr(filing, "form_type", None),
            str(e),
        )
        return IngestResult(filing_id=filing.id, ok=False, error=str(e))
    except Exception as e:  # pragma: no cover
        logger.exception(
            "Unexpected error downloading SEC filing | filing_id=%s cik=%s accession=%s doc=%s form_type=%s",
            getattr(filing, "id", None),
            cik,
            getattr(filing, "accession_number", None),
            doc_name,
            getattr(filing, "form_type", None),
        )
        return IngestResult(
            filing_id=filing.id, ok=False, error=f"{type(e).__name__}: {e}"
        )


def _db_ingest_diagnostics(*, session: SASession) -> None:
    """Log DB state that explains why ingest selected nothing."""

    try:
        total = session.query(func.count(SecFiling.id)).scalar() or 0
        pending = (
            session.query(func.count(SecFiling.id))
            .filter(
                or_(
                    SecFiling.fetch_status == None,  # noqa: E711
                    SecFiling.fetch_status == "pending",
                )
            )
            .scalar()
            or 0
        )
        logger.info(
            "DB diagnostics | sec_filings_total=%s pending_total=%s",
            int(total),
            int(pending),
        )

        rows = (
            session.query(SecFiling.fetch_status, func.count(SecFiling.id))
            .group_by(SecFiling.fetch_status)
            .order_by(func.count(SecFiling.id).desc())
            .all()
        )
        status_summary = ", ".join(
            f"{(r[0] if r[0] is not None else 'NULL')}={r[1]}" for r in rows
        )
        logger.info("DB diagnostics | fetch_status_counts={%s}", status_summary)

        missing_doc = (
            session.query(func.count(SecFiling.id))
            .filter(
                or_(
                    SecFiling.fetch_status == None,  # noqa: E711
                    SecFiling.fetch_status == "pending",
                )
            )
            .filter(
                or_(SecFiling.document_url == None, SecFiling.document_url == "")
            )  # noqa: E711
            .scalar()
            or 0
        )
        if int(missing_doc) > 0:
            logger.warning(
                "DB diagnostics | pending rows missing document_url=%s (these will be skipped)",
                int(missing_doc),
            )
    except Exception:
        logger.debug("DB diagnostics failed", exc_info=True)


def _requeue_failed_filings(
    *, session: SASession, limit: int, form_types: list[str] | None
) -> int:
    """Move a limited number of failed filings back to pending.

    Intended to keep external calls bounded while iterating on reliability.
    """

    q = session.query(SecFiling).filter(SecFiling.fetch_status == "failed")
    if form_types:
        q = q.filter(SecFiling.form_type.in_(form_types))

    # Oldest-first so we don't thrash the same recent failures.
    rows = q.order_by(SecFiling.id.asc()).limit(max(0, int(limit))).all()
    if not rows:
        return 0

    for f in rows:
        f.fetch_status = "pending"

    session.commit()
    logger.info(
        "Re-queued failed filings -> pending | count=%s form_types=%s limit=%s",
        len(rows),
        form_types,
        int(limit),
    )
    return len(rows)


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
        logger.info(
            "No pending filings selected | form_types=%s limit=%s | %s",
            form_types,
            limit,
            _log_paths_hint(),
        )
        _db_ingest_diagnostics(session=session)
        return {"selected": 0, "fetched": 0, "failed": 0}

    fetched = 0
    failed = 0

    logger.info(
        "Starting ingest | count=%s workers=%s form_types=%s limit=%s out_dir=%s sec_user_agent_set=%s | %s",
        len(filings),
        workers,
        form_types,
        limit,
        FORMS_DIR,
        bool(os.getenv("SEC_EDGAR_USER_AGENT")),
        _log_paths_hint(),
    )

    if not os.getenv("SEC_EDGAR_USER_AGENT"):
        logger.warning(
            "SEC_EDGAR_USER_AGENT is not set; SEC endpoints may return 403. "
            "Set SEC_EDGAR_USER_AGENT to something compliant (e.g. 'MyApp/1.0 you@example.com')."
        )

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
                logger.warning(
                    "Fetch failed | filing_id=%s accession=%s form_type=%s error=%s url=%s",
                    filing.id,
                    getattr(filing, "accession_number", None),
                    getattr(filing, "form_type", None),
                    res.error,
                    getattr(filing, "document_url", None),
                )

    session.commit()
    return {"selected": len(filings), "fetched": fetched, "failed": failed}


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    # Allow per-run log override without needing env vars.
    if args.log_level:
        os.environ["LOG_LEVEL"] = str(args.log_level)

    # Ensure logging configured as early as possible for console + file output.
    logger.info(
        "sec_api_ingest starting | cwd=%s argv=%s | %s",
        os.getcwd(),
        _argv_for_debug(argv),
        _log_paths_hint(),
    )
    _startup_diagnostics()
    logger.debug(
        "Parsed args | log_level=%s form_types=%s limit=%s workers=%s",
        getattr(args, "log_level", None),
        getattr(args, "form_types", None),
        getattr(args, "limit", None),
        getattr(args, "workers", None),
    )
    logger.info(
        "External-call safety | default_limit=%s(default via SEC_INGEST_DEFAULT_LIMIT) default_workers=%s(default via SEC_INGEST_DEFAULT_WORKERS)",
        int(os.getenv("SEC_INGEST_DEFAULT_LIMIT", "10")),
        int(os.getenv("SEC_INGEST_DEFAULT_WORKERS", "1")),
    )

    try:
        Base.metadata.create_all(bind=engine)

        with SessionLocal() as s:
            # Use CLI arg when provided; otherwise offer an interactive choice.
            form_types: list[str] | None = _parse_csv_list(args.form_types)
            if form_types is None and not args.form_types:
                try:
                    form_types = _prompt_form_types_interactive_with_availability(
                        session=s
                    )
                except (EOFError, KeyboardInterrupt):
                    raise SystemExit("Aborted.")

            # If nothing is pending and user requested it, re-queue a *small* number
            # of failed rows and try again. Keep this bounded by --limit.
            if getattr(args, "retry_failed", False):
                pending_now = (
                    s.query(func.count(SecFiling.id))
                    .filter(
                        or_(
                            SecFiling.fetch_status == None,  # noqa: E711
                            SecFiling.fetch_status == "pending",
                        )
                    )
                    .scalar()
                    or 0
                )
                if int(pending_now) == 0:
                    _requeue_failed_filings(
                        session=s, limit=int(args.limit), form_types=form_types
                    )

            summary = run_ingest(
                session=s,
                form_types=form_types,
                limit=int(args.limit),
                workers=int(args.workers),
            )

        logger.info(
            "sec_api_ingest complete | selected=%s fetched=%s failed=%s | %s",
            summary["selected"],
            summary["fetched"],
            summary["failed"],
            _log_paths_hint(),
        )

        # Console hint so interactive runs remain understandable even with INFO logs disabled.
        if summary.get("selected", 0) == 0:
            print("\nsec_api_ingest: no pending filings selected. Nothing to download.")
            print(
                "Tip: ensure another job populated sec_filings with fetch_status=pending, or run without a form-type filter."
            )
        else:
            print(
                f"\nsec_api_ingest: complete | selected={summary['selected']} fetched={summary['fetched']} failed={summary['failed']}"
            )
    except SystemExit:
        raise
    except Exception:
        # Always emit a traceback to both console and file.
        logger.exception("sec_api_ingest crashed | %s", _log_paths_hint())
        raise


if __name__ == "__main__":
    main()
