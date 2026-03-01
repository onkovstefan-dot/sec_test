"""Populate daily SEC-derived values into the SQLite database.

This script ingests SEC JSON payloads stored under `raw_data/` and flattens them into
primitives suitable for time-series querying:

- **entities**: a company/issuer identified by CIK
- **dates**: the observation date (typically `end` for facts or `filingDate`/`reportDate` for submissions)
- **value_names**: the metric/concept name (e.g. `us-gaap.Assets`)
- **units**: unit-of-measure for a value name (e.g. `USD`, `shares`, `NA`)
- **daily_values**: the actual value stored as text

Supported input shapes (auto-detected by folder name during recursive discovery):

- `raw_data/companyfacts/*.json`
  - walks `facts -> namespace -> metric -> units -> [points]`
  - maps each point with an `end` to `(entity, end-date, namespace.metric, unit, val)`

- `raw_data/submissions/*.json`
  - supports both the "full" shape with `filings.recent` and the flattened recent shape
  - maps `submissions.recent.<field>[i]` to `(entity, filingDate[i] or reportDate[i], field, NA, value)`

Database / correctness notes:

- Missing `Entity`, `Unit`, `ValueName`, and `DateEntry` rows are created on demand.
- Daily values are inserted using SQLite `INSERT OR IGNORE` to safely skip duplicates
  under the `daily_values` uniqueness constraint.
- Files that cannot be processed are *not* silently skipped; reasons and samples are
  logged under `logs/` (per-module log files) via the shared app logger.

If you change this file, run the test suite to validate parsing and DB behavior:

    pytest -q
"""

import sys
import os

# Allow running as standalone script
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import argparse
import json
import logging
import threading
import multiprocessing
from multiprocessing import Process
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from time import perf_counter

from sqlalchemy import create_engine, func, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SASession
from sqlalchemy.orm import sessionmaker

from logging_utils import get_logger
from models import Base
from models.daily_values import DailyValue
from models.dates import DateEntry
from models.entities import Entity
from models.entity_metadata import EntityMetadata
from models.file_processing import FileProcessing
from models.units import Unit
from models.value_names import ValueName
from models.entity_identifiers import EntityIdentifier
from utils.time_utils import parse_ymd_date, utcnow

import uuid


def _ts_now() -> str:
    """Human-friendly timestamp for console progress."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def timed_block(
    name: str,
    *,
    ping_every_seconds: int = 60,
    logger_obj: logging.Logger | None = None,
    print_fn=print,
):
    """Time a block of work.

    Prints start/end/elapsed and emits a periodic "ping" every `ping_every_seconds`
    while the block is still running.
    """

    start_wall = datetime.now()
    start = perf_counter()

    stop_event = threading.Event()

    def _ping_loop():
        # Wait first interval before printing a ping.
        while not stop_event.wait(ping_every_seconds):
            msg = f"[{_ts_now()}] ping: still running '{name}'..."
            # stdout disabled; keep logging only
            if logger_obj is not None:
                try:
                    logger_obj.info(msg)
                except Exception:
                    pass

    t = threading.Thread(target=_ping_loop, daemon=True)
    t.start()

    start_msg = f"[{_ts_now()}] START {name}"
    # stdout disabled; keep logging only
    if logger_obj is not None:
        logger_obj.info(start_msg)

    try:
        yield
    finally:
        stop_event.set()
        elapsed = perf_counter() - start
        end_wall = datetime.now()
        end_msg = (
            f"[{_ts_now()}] END {name} | started={start_wall.isoformat(timespec='seconds')} "
            f"ended={end_wall.isoformat(timespec='seconds')} elapsed={elapsed:.2f}s"
        )
        # stdout disabled; keep logging only
        if logger_obj is not None:
            logger_obj.info(end_msg)


def timed(
    name: str | None = None,
    *,
    ping_every_seconds: int = 60,
    logger_obj: logging.Logger | None = None,
    print_fn=print,
):
    """Decorator version of `timed_block` for functions/methods."""

    def _decorator(fn):
        label = name or fn.__name__

        @wraps(fn)
        def _wrapped(*args, **kwargs):
            with timed_block(
                label,
                ping_every_seconds=ping_every_seconds,
                logger_obj=logger_obj,
                print_fn=print_fn,
            ):
                return fn(*args, **kwargs)

        return _wrapped

    return _decorator


# Default process-sharding configuration.
#
# Priority when choosing worker count:
#   1) CLI arg --workers (if provided)
#   2) DEFAULT_WORKERS (if > 0)
#   3) Dynamic calculation (if DEFAULT_WORKERS <= 0)
#
# Set this to <= 0 to auto-pick based on available CPUs.
DEFAULT_WORKERS = -1


def _dynamic_default_workers() -> int:
    """Compute a safe default worker count from OS/hardware."""
    cpu = os.cpu_count() or 1
    # Avoid spinning up absurd numbers of processes by default.
    return max(1, min(int(cpu), 8))


def _resolve_workers(cli_workers: int | None) -> int:
    """Resolve the effective worker count based on CLI/constant/dynamic fallback."""
    if cli_workers is not None:
        workers = int(cli_workers)
    elif DEFAULT_WORKERS > 0:
        workers = int(DEFAULT_WORKERS)
    else:
        workers = _dynamic_default_workers()

    if workers <= 0:
        raise SystemExit("--workers must be a positive integer")
    return workers


# Internal-only flag used when this module spawns its own worker processes.
INTERNAL_ARG_WORKER_INDEX = "--_worker-index"

# Setup logging (shared app logger; per-process log files so multiprocessing workers don't interleave output.)
logger = get_logger(__name__, process_id=os.getpid())

# Previously we populated from raw_data/submissions.
# Companyfacts is where the numeric facts/metrics live.
RAW_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "raw_data")
COMPANYFACTS_DIR = os.path.join(RAW_DATA_DIR, "companyfacts")
SUBMISSIONS_DIR = os.path.join(RAW_DATA_DIR, "submissions")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sec.db")


# Backwards-compatible globals (used by unit tests and existing callers).
# NOTE: Multi-process mode uses its own per-process engine/session created in `_run()`.
engine = None
Session = None
session: SASession | None = None


def _init_default_db_globals() -> None:
    global engine, Session, session
    if engine is not None and Session is not None and session is not None:
        return
    engine = _make_engine(DB_PATH)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()


def _default_session(provided: SASession | None) -> SASession:
    """Return provided session or fall back to the module-level session.

    This keeps compatibility with unit tests that monkeypatch `utils.populate_daily_values.session`.
    """
    if provided is not None:
        return provided
    _init_default_db_globals()
    assert session is not None
    return session


def _make_engine(db_path: str):
    """Create a SQLite engine with safer defaults for concurrent writers."""
    # `check_same_thread=False` is important because SQLAlchemy may use connection
    # pool internals that otherwise trip SQLite thread checks.
    #
    # For multi-process, each process has its own engine anyway.
    eng = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )
    return eng


def _configure_sqlite_for_concurrency(session: SASession) -> None:
    """Apply PRAGMAs that reduce 'database is locked' risk."""
    try:
        session.execute(text("PRAGMA journal_mode=WAL;"))
        session.execute(text("PRAGMA synchronous=NORMAL;"))
        session.execute(text("PRAGMA busy_timeout=30000;"))
    except Exception:
        # Not fatal; continue with defaults.
        pass


def _chunked_files(
    files: list[tuple[str, str, str]], *, workers: int, worker_index: int
) -> list[tuple[str, str, str]]:
    """Deterministically shard a sorted file list across workers.

    Sharding by index (round-robin) avoids giving one worker all large files if the list
    is grouped by folder.
    """
    if workers <= 1:
        return files
    if worker_index < 0 or worker_index >= workers:
        raise ValueError("worker_index must be in [0, workers)")
    return [t for i, t in enumerate(files) if (i % workers) == worker_index]


def _safe_str(val, max_len: int = 4000) -> str:
    """Convert arbitrary JSON value to a reasonably-sized string for storage."""
    if val is None:
        return ""
    if isinstance(val, (str, int, float, bool)):
        s = str(val)
    else:
        # fallback for lists/dicts
        try:
            s = json.dumps(val, ensure_ascii=False)
        except Exception:
            s = str(val)
    return s[:max_len]


def _insert_daily_values_ignore_bulk(
    session: SASession | None, rows: list[dict]
) -> int:
    session = _default_session(session)
    """Bulk insert daily_values rows using SQLite INSERT OR IGNORE.

    SQLite enforces a limit on the number of bound parameters per statement
    (typically 999 unless SQLite was compiled with a higher value). Since each
    `daily_values` row binds 4 columns (entity_id, date_id, value_name_id, value),
    we must chunk large inserts to stay below that limit.

    Returns best-effort count of inserted rows.
    """
    if not rows:
        return 0

    # 4 bound parameters per row for the statement we generate.
    # Keep some margin to account for any additional parameters SQLAlchemy might add.
    SQLITE_MAX_VARS_DEFAULT = 999
    PARAMS_PER_ROW = 4
    max_rows_per_chunk = max(1, (SQLITE_MAX_VARS_DEFAULT // PARAMS_PER_ROW) - 5)

    inserted = 0
    for i in range(0, len(rows), max_rows_per_chunk):
        chunk = rows[i : i + max_rows_per_chunk]
        stmt = sqlite_insert(DailyValue).values(chunk).prefix_with("OR IGNORE")
        res = session.execute(stmt)
        # Ensure SQLite has actually executed the INSERT so rowcount is accurate.
        session.flush()
        inserted += int(getattr(res, "rowcount", 0) or 0)

    return inserted


# Keep the single-row helper for potential future/diagnostics use.
def _insert_daily_value_ignore(
    session: SASession | None,
    entity_id: int,
    date_id: int,
    value_name_id: int,
    value: str,
) -> bool:
    session = _default_session(session)
    """Insert into daily_values, ignoring unique-constraint duplicates.

    Returns True if inserted, False if ignored as duplicate.
    """
    stmt = (
        sqlite_insert(DailyValue)
        .values(
            entity_id=entity_id,
            date_id=date_id,
            value_name_id=value_name_id,
            value=value,
        )
        .prefix_with("OR IGNORE")
    )
    res = session.execute(stmt)
    # SQLite rowcount == 1 if inserted, 0 if ignored
    return bool(getattr(res, "rowcount", 0))


def _normalize_identifier_value(scheme: str, value: str) -> str:
    """Normalize identifier values for consistent strict matching."""
    v = (value or "").strip()
    if not v:
        return v

    scheme_l = (scheme or "").strip().lower()

    if scheme_l in {"sec_cik", "cik"}:
        # store CIK as 10-digit zero padded
        n = _normalize_cik(v)
        return n or v

    if scheme_l in {"gleif_lei", "lei"}:
        return v.upper()

    # Default: trim only.
    return v


def _scheme_alias(scheme: str) -> str:
    """Map common aliases onto canonical scheme names."""
    s = (scheme or "").strip().lower()
    if s in {"cik", "sec", "sec-cik", "sec_cik"}:
        return "sec_cik"
    if s in {"lei", "gleif", "gleif-lei", "gleif_lei"}:
        return "gleif_lei"
    return s


def _get_or_create_entity_identifier(
    session: SASession,
    *,
    entity_id: int,
    scheme: str,
    value: str,
    country: str | None = None,
    issuer: str | None = None,
) -> EntityIdentifier:
    scheme_n = _scheme_alias(scheme)
    value_n = _normalize_identifier_value(scheme_n, value)

    with session.no_autoflush:
        existing = (
            session.query(EntityIdentifier)
            .filter_by(scheme=scheme_n, value=value_n)
            .first()
        )
    if existing:
        # If it already exists but points elsewhere, keep strictness and surface conflict.
        if existing.entity_id != entity_id:
            raise IntegrityError(
                f"Identifier conflict: {scheme_n}:{value_n} already belongs to entity_id={existing.entity_id}",
                params=None,
                orig=None,
            )
        return existing

    ident = EntityIdentifier(
        entity_id=entity_id,
        scheme=scheme_n,
        value=value_n,
        country=country,
        issuer=issuer,
    )
    session.add(ident)
    session.flush()
    return ident


def get_or_create_entity_by_identifier(
    *,
    scheme: str,
    value: str,
    session: SASession | None = None,
    country: str | None = None,
    issuer: str | None = None,
    create_if_missing: bool = True,
) -> Entity:
    """Resolve an Entity via a strict external identifier, creating if missing.

    This is the preferred entry-point for strict matching across heterogeneous
    sources.

    Matching rules:
    - Identifiers are normalized based on `scheme`.
    - The `entity_identifiers` table enforces uniqueness on (scheme, value).

    Args:
        scheme: Canonical identifier scheme (e.g. 'sec_cik', 'gleif_lei').
        value: Raw identifier value.
        country: Optional country context to record.
        issuer: Optional issuer context to record.
        create_if_missing: If False, raises LookupError when identifier not found.

    Returns:
        Entity

    Raises:
        LookupError: if create_if_missing is False and identifier doesn't exist.
        IntegrityError: if an identifier conflict is detected.
    """

    session = _default_session(session)

    scheme_n = _scheme_alias(scheme)
    value_n = _normalize_identifier_value(scheme_n, value)
    if not scheme_n or not value_n:
        raise ValueError("scheme and value must be non-empty")

    with session.no_autoflush:
        ident = (
            session.query(EntityIdentifier)
            .filter_by(scheme=scheme_n, value=value_n)
            .first()
        )

    if ident is not None:
        with session.no_autoflush:
            entity = session.query(Entity).filter_by(id=ident.entity_id).first()
        if entity is None:
            # DB inconsistency; fail loudly.
            raise LookupError(
                f"Orphan entity_identifiers row: {scheme_n}:{value_n} -> entity_id={ident.entity_id}"
            )

        # Backfill canonical UUID if this is an older row.
        if not getattr(entity, "canonical_uuid", None):
            entity.canonical_uuid = str(uuid.uuid4())
            session.flush()

        # Optionally backfill context.
        changed = False
        if country and not ident.country:
            ident.country = country
            changed = True
        if issuer and not ident.issuer:
            ident.issuer = issuer
            changed = True
        if changed:
            session.flush()

        return entity

    if not create_if_missing:
        raise LookupError(f"No entity found for identifier {scheme_n}:{value_n}")

    # Create entity + identifier atomically inside caller's transaction.
    entity = Entity(canonical_uuid=str(uuid.uuid4()))

    # Keep legacy convenience field populated when available.
    if scheme_n == "sec_cik":
        entity.cik = value_n

    session.add(entity)
    session.flush()

    _get_or_create_entity_identifier(
        session,
        entity_id=entity.id,
        scheme=scheme_n,
        value=value_n,
        country=country,
        issuer=issuer,
    )

    return entity


def get_or_create_entity(
    cik,
    company_name: str | None = None,
    metadata: dict | None = None,
    session: SASession | None = None,
):
    session = _default_session(session)
    """Get an `Entity` by CIK or create it.

    Additionally:
    - Ensures `entities.canonical_uuid` is set.
    - Ensures an `entity_identifiers` row exists for the SEC CIK.

    Optimized: avoids committing inside helper; caller controls transaction.
    Also backfills `entity_metadata` fields when provided.

    Args:
        cik: The CIK identifier
        company_name: Company name (legacy parameter, also in metadata dict)
        metadata: Dict of metadata fields to populate in entity_metadata table
    """

    cik10 = _normalize_cik(cik)
    if not cik10:
        raise ValueError(f"Invalid CIK: {cik!r}")

    entity = get_or_create_entity_by_identifier(
        scheme="sec_cik",
        value=cik10,
        session=session,
        country="US",
        issuer="sec",
        create_if_missing=True,
    )

    # Create/backfill metadata (1:1)
    if company_name or metadata:
        with session.no_autoflush:
            meta = session.query(EntityMetadata).filter_by(entity_id=entity.id).first()
        if not meta:
            meta = EntityMetadata(entity_id=entity.id)
            session.add(meta)
            session.flush()

        # Update company_name from either parameter
        if company_name and not meta.company_name:
            meta.company_name = company_name

        # Update all metadata fields if provided
        if metadata:
            for key, value in metadata.items():
                if value and not getattr(meta, key, None):
                    setattr(meta, key, value)
            session.flush()

    return entity


def get_or_create_unit(name: str | None, session: SASession | None = None):
    session = _default_session(session)
    """Get a `Unit` by name or create it.

    Optimized: avoids committing inside helper; caller controls transaction.
    """
    unit_name = (name or "NA").strip() or "NA"
    with session.no_autoflush:
        unit = session.query(Unit).filter_by(name=unit_name).first()
    if not unit:
        unit = Unit(name=unit_name)
        session.add(unit)
        session.flush()
    return unit


def get_or_create_value_name(
    name, unit_id: int | None = None, session: SASession | None = None
):
    session = _default_session(session)
    """Get a `ValueName` by SEC concept name or create it.

    Optimized: avoids committing inside helper; caller controls transaction.
    """
    with session.no_autoflush:
        value_name = session.query(ValueName).filter_by(name=name).first()
    if not value_name:
        value_name = ValueName(
            name=name,
            unit_id=unit_id,
            source="sec",
            added_on=utcnow(),
        )
        session.add(value_name)
        session.flush()
        return value_name

    # backfill unit_id if missing
    if unit_id and getattr(value_name, "unit_id", None) is None:
        value_name.unit_id = unit_id
        session.flush()

    return value_name


def get_or_create_date_entry(date_str, session: SASession | None = None):
    session = _default_session(session)
    """Get a `DateEntry` by `YYYY-MM-DD` string or create it.

    Optimized: avoids committing inside helper; caller controls transaction.
    Returns None if the date string cannot be parsed.
    """
    try:
        date_obj = parse_ymd_date(date_str)
    except Exception as e:
        logger.error(f"Invalid date format: {date_str} - {e}")
        return None
    with session.no_autoflush:
        date_entry = session.query(DateEntry).filter_by(date=date_obj).first()
    if not date_entry:
        date_entry = DateEntry(date=date_obj)
        session.add(date_entry)
        session.flush()
    return date_entry


def delete_all_daily_values(session: SASession | None = None):
    session = _default_session(session)
    """Delete all rows from `daily_values`.

    Intended as a one-off helper during development/troubleshooting.
    """
    try:
        num_deleted = session.query(DailyValue).delete()
        session.commit()
        print(f"Deleted {num_deleted} rows from DailyValue table.")
        logger.warning(
            f"Deleted {num_deleted} rows from DailyValue table "
            f"via delete_all_daily_values()."
        )
    except Exception as e:
        session.rollback()
        print(f"Error deleting DailyValue data: {e}")
        logger.error(f"Error deleting DailyValue data: {e}", exc_info=True)


def _is_nonempty_dict(v) -> bool:
    """True if `v` is a dict and not empty."""
    return isinstance(v, dict) and bool(v)


def _is_list(v) -> bool:
    """True if `v` is a list."""
    return isinstance(v, list)


def _log_unprocessed(
    *,
    source: str,
    filename: str,
    reason: str,
    details: str,
    skip_reasons: Counter,
    skip_reason_samples: dict[str, list[str]],
    error_files: list[str],
) -> None:
    """Log an unprocessed file with a structured reason.

    Also updates counters and keeps a small sample list per reason.
    """
    skip_reasons[reason] += 1
    if len(skip_reason_samples[reason]) < 10:
        skip_reason_samples[reason].append(filename)
    logger.warning(
        "Unprocessed file [%s] %s: %s | %s", source, filename, reason, details
    )
    error_files.append(f"{source}:{filename}")


def _normalize_cik(raw) -> str | None:
    """Normalize a CIK into 10-digit, zero-padded form.

    Accepts ints, numeric strings, or strings like `CIK0000123456`.
    """
    if raw is None:
        return None
    try:
        return str(int(raw)).zfill(10)
    except Exception:
        s = str(raw).strip()
        if not s:
            return None
        # keep digits only if someone passed 'CIK0000...'
        if s.startswith("CIK"):
            s = s[3:]
        digits = "".join(ch for ch in s if ch.isdigit())
        return digits.zfill(10) if digits else None


def infer_cik_from_filename(name: str) -> str | None:
    """Infer a CIK from a filename like `CIK0000123456.json` (digits only)."""
    base = os.path.basename(name)
    if not base.startswith("CIK"):
        return None
    digits = []
    for ch in base[3:]:
        if ch.isdigit():
            digits.append(ch)
        else:
            break
    return "".join(digits) or None


def extract_metadata_from_submissions(data: dict) -> dict:
    """Extract entity metadata fields from a submissions JSON payload.

    Returns a dict with keys matching EntityMetadata column names.
    """
    metadata = {}

    # Company name
    name = data.get("name") or data.get("entityName") or data.get("companyName")
    if name and isinstance(name, str):
        metadata["company_name"] = name.strip()

    # SIC (Standard Industrial Classification)
    if data.get("sic"):
        metadata["sic"] = str(data["sic"]).strip()
    if data.get("sicDescription"):
        metadata["sic_description"] = str(data["sicDescription"]).strip()

    # Incorporation and fiscal info
    if data.get("stateOfIncorporation"):
        metadata["state_of_incorporation"] = str(data["stateOfIncorporation"]).strip()
    if data.get("stateOfIncorporationDescription"):
        metadata["state_of_incorporation_description"] = str(
            data["stateOfIncorporationDescription"]
        ).strip()
    if data.get("fiscalYearEnd"):
        metadata["fiscal_year_end"] = str(data["fiscalYearEnd"]).strip()

    # Filer category and entity type
    if data.get("category"):
        metadata["filer_category"] = str(data["category"]).strip()
    if data.get("entityType"):
        metadata["entity_type"] = str(data["entityType"]).strip()

    # Contact information
    if data.get("website"):
        metadata["website"] = str(data["website"]).strip()
    if data.get("phone"):
        metadata["phone"] = str(data["phone"]).strip()
    if data.get("ein"):
        metadata["ein"] = str(data["ein"]).strip()

    # Additional entity info
    if data.get("lei"):
        metadata["lei"] = str(data["lei"]).strip()
    if data.get("investorWebsite"):
        metadata["investor_website"] = str(data["investorWebsite"]).strip()
    if data.get("description"):
        metadata["entity_description"] = str(data["description"]).strip()
    if data.get("ownerOrg"):
        metadata["owner_organization"] = str(data["ownerOrg"]).strip()

    # Regulatory flags
    if data.get("flags"):
        metadata["sec_flags"] = str(data["flags"]).strip()
    if "insiderTransactionForOwnerExists" in data:
        metadata["has_insider_transactions_as_owner"] = int(
            data["insiderTransactionForOwnerExists"]
        )
    if "insiderTransactionForIssuerExists" in data:
        metadata["has_insider_transactions_as_issuer"] = int(
            data["insiderTransactionForIssuerExists"]
        )

    # Trading info - serialize lists as JSON
    if data.get("tickers") and isinstance(data["tickers"], list):
        metadata["tickers"] = json.dumps(data["tickers"])
    if data.get("exchanges") and isinstance(data["exchanges"], list):
        metadata["exchanges"] = json.dumps(data["exchanges"])

    # Former names - serialize as JSON
    if data.get("formerNames") and isinstance(data["formerNames"], list):
        # Convert ISO date strings to YYYY-MM-DD format for readability
        former_names = []
        for fn in data["formerNames"]:
            if isinstance(fn, dict) and fn.get("name"):
                entry = {"name": fn["name"]}
                # Parse ISO dates if present
                if fn.get("from"):
                    entry["from"] = (
                        fn["from"][:10] if len(fn["from"]) >= 10 else fn["from"]
                    )
                if fn.get("to"):
                    entry["to"] = fn["to"][:10] if len(fn["to"]) >= 10 else fn["to"]
                former_names.append(entry)
        if former_names:
            metadata["former_names"] = json.dumps(former_names)

    # Business address
    addresses = data.get("addresses", {})
    if isinstance(addresses, dict):
        business = addresses.get("business", {})
        if isinstance(business, dict):
            if business.get("street1"):
                metadata["business_street1"] = str(business["street1"]).strip()
            if business.get("street2"):
                metadata["business_street2"] = str(business["street2"]).strip()
            if business.get("city"):
                metadata["business_city"] = str(business["city"]).strip()
            if business.get("stateOrCountry"):
                metadata["business_state"] = str(business["stateOrCountry"]).strip()
            if business.get("zipCode"):
                metadata["business_zipcode"] = str(business["zipCode"]).strip()
            # Some submissions have country field
            if business.get("country"):
                metadata["business_country"] = str(business["country"]).strip()

        # Mailing address (may differ from business address)
        mailing = addresses.get("mailing", {})
        if isinstance(mailing, dict):
            if mailing.get("street1"):
                metadata["mailing_street1"] = str(mailing["street1"]).strip()
            if mailing.get("street2"):
                metadata["mailing_street2"] = str(mailing["street2"]).strip()
            if mailing.get("city"):
                metadata["mailing_city"] = str(mailing["city"]).strip()
            if mailing.get("stateOrCountry"):
                metadata["mailing_state"] = str(mailing["stateOrCountry"]).strip()
            if mailing.get("zipCode"):
                metadata["mailing_zipcode"] = str(mailing["zipCode"]).strip()
            if mailing.get("country"):
                metadata["mailing_country"] = str(mailing["country"]).strip()

    return metadata


def extract_entity_identity(
    data: dict, filename: str
) -> tuple[str | None, str | None, dict]:
    """Extract (cik10, company_name, metadata_dict) from payload, falling back to filename.

    Returns:
        - cik: normalized 10-digit CIK
        - company_name: company name string or None
        - metadata: dict of additional metadata fields (empty dict if none found)
    """
    cik = _normalize_cik(data.get("cik"))
    if not cik:
        inferred = infer_cik_from_filename(filename)
        cik = _normalize_cik(inferred)
    company_name = data.get("entityName") or data.get("name") or data.get("companyName")
    company_name = company_name.strip() if isinstance(company_name, str) else None

    # Extract metadata if this is a submissions file (has more fields)
    metadata = {}
    if data.get("sic") or data.get("stateOfIncorporation") or data.get("addresses"):
        metadata = extract_metadata_from_submissions(data)

    return cik, company_name, metadata


def _resolve_recent_payload(data: dict):
    """Resolve the submissions "recent" payload and schema name.

    Returns (schema_name, recent_dict_or_none).
    """
    if not isinstance(data, dict):
        return "non_dict", None

    filings = data.get("filings")
    if isinstance(filings, dict):
        recent = filings.get("recent")
        if isinstance(recent, dict):
            return "full_submissions", recent

    if (
        "filings" not in data
        and isinstance(data.get("filingDate"), list)
        and ("accessionNumber" in data or "form" in data)
    ):
        return "flattened_recent", data

    return "unknown", None


def iter_companyfacts_points(facts: dict):
    """Iterate companyfacts points.

    Yields `(value_name, unit_name, end_date, raw_val)`.
    """
    if not isinstance(facts, dict):
        return
    for namespace, metrics in facts.items():
        if not isinstance(metrics, dict):
            continue
        for metric, metric_obj in metrics.items():
            if not isinstance(metric_obj, dict):
                continue
            units = metric_obj.get("units")
            if not isinstance(units, dict) or not units:
                continue
            for unit, points in units.items():
                if not isinstance(points, list):
                    continue
                value_name = f"{namespace}.{metric}"
                for p in points:
                    if not isinstance(p, dict):
                        continue
                    end = p.get("end")
                    if not end:
                        continue
                    val = p.get("val")
                    yield value_name, unit, end, val


def iter_submissions_recent_points(recent: dict):
    """Iterate submissions `recent` arrays.

    Yields `(value_name, unit_name, date_str_or_none, raw_val)`.
    Values without a corresponding `filingDate`/`reportDate` yield `date_str_or_none=None`.
    """
    if not isinstance(recent, dict) or not recent:
        return

    filing_dates = (
        recent.get("filingDate") if isinstance(recent.get("filingDate"), list) else []
    )
    report_dates = (
        recent.get("reportDate") if isinstance(recent.get("reportDate"), list) else []
    )

    def _date_for_index(i: int) -> str | None:
        if i < len(filing_dates) and filing_dates[i]:
            return filing_dates[i]
        if i < len(report_dates) and report_dates[i]:
            return report_dates[i]
        return None

    for key, arr in recent.items():
        if not isinstance(arr, list):
            continue
        if key in ("filingDate", "reportDate"):
            continue

        value_name = f"submissions.recent.{key}"
        for i, raw_val in enumerate(arr):
            date_str = _date_for_index(i)
            if not date_str:
                yield value_name, "NA", None, raw_val
            else:
                yield value_name, "NA", date_str, raw_val


@timed("process_companyfacts_file", logger_obj=logger)
def process_companyfacts_file(
    *,
    data: dict,
    source: str,
    filename: str,
    entity_id: int,
    get_unit_id_cached,
    get_value_name_id_cached,
    get_date_id_cached,
    session: SASession | None = None,
) -> tuple[int, int]:
    session = _default_session(session)
    """Process a single companyfacts JSON payload.

    Optimized: batch INSERT OR IGNORE into daily_values per file.

    Returns `(planned_inserts, duplicates_skipped)`.
    """
    facts = data.get("facts")
    if not _is_nonempty_dict(facts):
        return 0, 0

    rows: list[dict] = []
    inserts_planned = 0

    for value_name, unit_name, end_date, raw_val in iter_companyfacts_points(facts):
        date_id = get_date_id_cached(end_date)
        if not date_id:
            continue
        unit_id = get_unit_id_cached(unit_name)
        vn_id = get_value_name_id_cached(value_name, unit_id)
        inserts_planned += 1
        rows.append(
            dict(
                entity_id=entity_id,
                date_id=date_id,
                value_name_id=vn_id,
                value=_safe_str(raw_val),
            )
        )

    inserted = _insert_daily_values_ignore_bulk(session, rows)
    duplicates = max(inserts_planned - inserted, 0)
    return inserts_planned, duplicates


@timed("process_submissions_file", logger_obj=logger)
def process_submissions_file(
    *,
    data: dict,
    source: str,
    filename: str,
    entity_id: int,
    get_unit_id_cached,
    get_value_name_id_cached,
    get_date_id_cached,
    session: SASession | None = None,
) -> tuple[str, int, int, str | None]:
    session = _default_session(session)
    """Process a single submissions JSON payload.

    Optimized: batch INSERT OR IGNORE into daily_values per file.

    Returns `(schema, planned_inserts, duplicates_skipped, unprocessed_reason_or_none)`.
    """
    schema, recent = _resolve_recent_payload(data)
    if not _is_nonempty_dict(recent):
        return schema, 0, 0, "unknown_submissions_schema"

    filing_dates = (
        recent.get("filingDate") if isinstance(recent.get("filingDate"), list) else []
    )
    report_dates = (
        recent.get("reportDate") if isinstance(recent.get("reportDate"), list) else []
    )
    if not filing_dates and not report_dates:
        return schema, 0, 0, "submissions_missing_dates"

    rows: list[dict] = []
    inserts_planned = 0

    na_unit_id = get_unit_id_cached("NA")

    for value_name, unit_name, date_str, raw_val in iter_submissions_recent_points(
        recent
    ):
        if not date_str:
            continue
        date_id = get_date_id_cached(date_str)
        if not date_id:
            continue
        vn_id = get_value_name_id_cached(value_name, na_unit_id)
        inserts_planned += 1
        rows.append(
            dict(
                entity_id=entity_id,
                date_id=date_id,
                value_name_id=vn_id,
                value=_safe_str(raw_val),
            )
        )

    inserted = _insert_daily_values_ignore_bulk(session, rows)
    duplicates = max(inserts_planned - inserted, 0)

    return schema, inserts_planned, duplicates, None


@timed("discover_json_files", logger_obj=logger)
def discover_json_files(root_dir: str):
    """Recursively find JSON files under `root_dir`.

    Returns a sorted list of `(source_folder_name, absolute_path, filename)` tuples.
    """
    found: list[tuple[str, str, str]] = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            if not fn.lower().endswith(".json"):
                continue
            src = os.path.basename(dirpath) or "raw_data"
            full_path = os.path.join(dirpath, fn)
            found.append((src, full_path, fn))
    found.sort(key=lambda t: (t[0], t[2]))
    return found


def _source_file_key(source: str, rel_path: str) -> str:
    """Stable identifier to track a processed file.

    Use the rel_path under raw_data; include source to guard against weird layouts.
    """
    return f"{source}:{rel_path}"


def _mark_file_processed(
    session: SASession | None, entity_id: int, source_file: str
) -> None:
    session = _default_session(session)
    """Insert a processed marker row (idempotent)."""
    stmt = (
        sqlite_insert(FileProcessing)
        .values(entity_id=entity_id, source_file=source_file)
        .prefix_with("OR IGNORE")
    )
    session.execute(stmt)


def _load_processed_file_keys(session: SASession | None = None) -> set[str]:
    session = _default_session(session)
    """Load processed file keys into memory for fast skipping."""
    try:
        rows = session.query(FileProcessing.source_file).all()
        return {r[0] for r in rows}
    except Exception:
        # If table doesn't exist for some reason, Base.metadata.create_all should have
        # created it; but play safe.
        return set()


def _prompt_yes_no(prompt: str, *, default_no: bool = True) -> bool:
    """Interactive confirmation prompt.

    Returns True if user confirms.
    """
    suffix = "[y/N]" if default_no else "[Y/n]"
    while True:
        try:
            resp = input(f"{prompt} {suffix}: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        if not resp:
            return not default_no
        if resp in {"y", "yes"}:
            return True
        if resp in {"n", "no"}:
            return False
        print("Please enter 'y' or 'n'.")


def _summarize_run_setup(*, db_path: str, workers: int) -> dict:
    """Compute a run summary for an interactive confirmation prompt.

    Summary is best-effort and intended for human sanity-checking.
    """
    eng = _make_engine(db_path)
    Base.metadata.create_all(eng)
    SessionLocal = sessionmaker(bind=eng, future=True)

    with SessionLocal() as s:
        _configure_sqlite_for_concurrency(s)
        s.commit()

        files_all = discover_json_files(RAW_DATA_DIR)
        # Match the ordering used by workers.
        files_all = sorted(files_all, key=lambda t: (t[0], t[1], t[2]))

        processed = _load_processed_file_keys(s)

        remaining_files: list[tuple[str, str, str]] = []
        for source, file_path, filename in files_all:
            rel_path = os.path.relpath(file_path, RAW_DATA_DIR)
            file_key = _source_file_key(source, rel_path)
            if file_key in processed:
                continue
            remaining_files.append((source, file_path, filename))

        total = len(files_all)
        skipped = total - len(remaining_files)
        left = len(remaining_files)

        # Estimated distribution by deterministic sharding.
        est_per_worker = []
        if workers <= 1:
            est_per_worker = [left]
        else:
            for wi in range(workers):
                est_per_worker.append(
                    len(
                        _chunked_files(
                            remaining_files, workers=workers, worker_index=wi
                        )
                    )
                )

        return {
            "workers": workers,
            "total_files": total,
            "skipped_files": skipped,
            "files_left": left,
            "est_per_worker": est_per_worker,
        }


def _run(
    *,
    workers: int = 1,
    worker_index: int = 0,
    db_path: str = DB_PATH,
    files_override: list[tuple[str, str, str]] | None = None,
) -> None:
    """Run a single worker (process) over its deterministic shard of files."""

    engine = _make_engine(db_path)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)

    with SessionLocal() as session:
        _configure_sqlite_for_concurrency(session)
        session.commit()

        with timed_block("populate_daily_values total", logger_obj=logger):
            if files_override is None:
                files = discover_json_files(RAW_DATA_DIR)
                # Deterministic ordering + deterministic sharding reduces overlap and makes
                # reruns/debugging easier.
                files = sorted(files, key=lambda t: (t[0], t[1], t[2]))
                files = _chunked_files(
                    files, workers=workers, worker_index=worker_index
                )
            else:
                files = files_override

            processed = _load_processed_file_keys(session)

            total_files = len(files)
            error_files: list[str] = []

            total_successful_inserts = 0
            total_duplicates = 0

            logger.info(
                "Worker %s/%s starting. Assigned files=%s (processed set size=%s)",
                worker_index + 1,
                workers,
                total_files,
                len(processed),
            )

            skip_reasons = Counter()
            error_reasons = Counter()
            skip_reason_samples: dict[str, list[str]] = defaultdict(list)

            entity_cache: dict[str, int] = {}
            value_name_cache: dict[tuple[str, int | None], int] = {}
            unit_cache: dict[str, int] = {}
            date_cache: dict[str, int] = {}

            totals = Counter()
            verbose_per_file = False

            def get_entity_id_cached(
                cik: str, company_name: str | None = None, metadata: dict | None = None
            ) -> int:
                key = cik
                if key in entity_cache:
                    if company_name or metadata:
                        get_or_create_entity(
                            cik,
                            company_name=company_name,
                            metadata=metadata,
                            session=session,
                        )
                    return entity_cache[key]
                entity_id = get_or_create_entity(
                    cik,
                    company_name=company_name,
                    metadata=metadata,
                    session=session,
                ).id
                entity_cache[key] = entity_id
                return entity_id

            def get_unit_id_cached(unit_name: str | None) -> int:
                key = (unit_name or "NA").strip() or "NA"
                if key in unit_cache:
                    return unit_cache[key]
                unit_id = get_or_create_unit(key, session=session).id
                unit_cache[key] = unit_id
                return unit_id

            def get_value_name_id_cached(name: str, unit_id: int | None) -> int:
                key = (name, unit_id)
                if key in value_name_cache:
                    return value_name_cache[key]
                vn_id = get_or_create_value_name(
                    name, unit_id=unit_id, session=session
                ).id
                value_name_cache[key] = vn_id
                return vn_id

            def get_date_id_cached(date_str: str) -> int | None:
                if date_str in date_cache:
                    return date_cache[date_str]
                date_entry = get_or_create_date_entry(date_str, session=session)
                if not date_entry:
                    return None
                date_cache[date_str] = date_entry.id
                return date_entry.id

            get_unit_id_cached("NA")

            for idx, (source, file_path, filename) in enumerate(files, 1):
                t0 = perf_counter()

                rel_path = os.path.relpath(file_path, RAW_DATA_DIR)
                file_key = _source_file_key(source, rel_path)
                if file_key in processed:
                    continue

                if idx % 100 == 0:
                    logger.info(
                        "Worker %s/%s progress: %s/%s files",
                        worker_index + 1,
                        workers,
                        idx,
                        total_files,
                    )

                if verbose_per_file:
                    logger.info(
                        "Worker %s: Processing file %s/%s: [%s] %s",
                        worker_index + 1,
                        idx,
                        total_files,
                        source,
                        rel_path,
                    )

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if not isinstance(data, dict):
                        _log_unprocessed(
                            source=source,
                            filename=rel_path,
                            reason="non_dict_json",
                            details=f"type={type(data).__name__}",
                            skip_reasons=skip_reasons,
                            skip_reason_samples=skip_reason_samples,
                            error_files=error_files,
                        )
                        continue

                    cik, company_name, metadata = extract_entity_identity(
                        data, filename
                    )
                    if not cik:
                        _log_unprocessed(
                            source=source,
                            filename=rel_path,
                            reason="missing_cik_and_cannot_infer",
                            details=f"top_keys={sorted(list(data.keys()))[:30]}",
                            skip_reasons=skip_reasons,
                            skip_reason_samples=skip_reason_samples,
                            error_files=error_files,
                        )
                        continue

                    entity_id = get_entity_id_cached(
                        cik, company_name=company_name, metadata=metadata
                    )

                    inserts_planned = 0
                    duplicates = 0

                    if source == "companyfacts":
                        if not _is_nonempty_dict(data.get("facts")):
                            _log_unprocessed(
                                source=source,
                                filename=rel_path,
                                reason="missing_facts",
                                details=f"cik={cik} entityName={company_name} top_keys={sorted(list(data.keys()))[:30]}",
                                skip_reasons=skip_reasons,
                                skip_reason_samples=skip_reason_samples,
                                error_files=error_files,
                            )
                            continue

                        inserts_planned, duplicates = process_companyfacts_file(
                            session=session,
                            data=data,
                            source=source,
                            filename=rel_path,
                            entity_id=entity_id,
                            get_unit_id_cached=get_unit_id_cached,
                            get_value_name_id_cached=get_value_name_id_cached,
                            get_date_id_cached=get_date_id_cached,
                        )

                    elif source == "submissions":
                        schema, inserts_planned, duplicates, unprocessed_reason = (
                            process_submissions_file(
                                session=session,
                                data=data,
                                source=source,
                                filename=rel_path,
                                entity_id=entity_id,
                                get_unit_id_cached=get_unit_id_cached,
                                get_value_name_id_cached=get_value_name_id_cached,
                                get_date_id_cached=get_date_id_cached,
                            )
                        )
                        if unprocessed_reason:
                            _log_unprocessed(
                                source=source,
                                filename=rel_path,
                                reason=unprocessed_reason,
                                details=f"schema={schema} keys={sorted(list(data.keys()))[:30]}",
                                skip_reasons=skip_reasons,
                                skip_reason_samples=skip_reason_samples,
                                error_files=error_files,
                            )
                            continue

                    else:
                        _log_unprocessed(
                            source=source,
                            filename=rel_path,
                            reason="unknown_source",
                            details=f"No handler for source folder '{source}'",
                            skip_reasons=skip_reasons,
                            skip_reason_samples=skip_reason_samples,
                            error_files=error_files,
                        )
                        continue

                    _mark_file_processed(
                        session, entity_id=entity_id, source_file=file_key
                    )

                    try:
                        session.commit()
                    except IntegrityError:
                        session.rollback()
                        error_reasons["IntegrityError"] += 1
                        error_files.append(f"{source}:{rel_path}")
                        continue
                    except Exception as e:
                        session.rollback()
                        error_reasons[type(e).__name__] += 1
                        logger.error(
                            "Commit failed for file %s: %s", rel_path, e, exc_info=True
                        )
                        error_files.append(f"{source}:{rel_path}")
                        continue

                    processed.add(file_key)

                    inserted = max(inserts_planned - duplicates, 0)
                    total_successful_inserts += inserted
                    total_duplicates += duplicates

                    totals["files_processed"] += 1
                    totals["inserted"] += inserted
                    totals["duplicates"] += duplicates

                    logger.info(
                        "Worker %s completed file %s source=%s: inserted=%s dup=%s elapsed=%.2fs",
                        worker_index + 1,
                        rel_path,
                        source,
                        inserted,
                        duplicates,
                        perf_counter() - t0,
                    )

                except Exception as e:
                    session.rollback()
                    error_reasons[type(e).__name__] += 1
                    logger.error(
                        "Error processing file %s: %s", rel_path, e, exc_info=True
                    )
                    error_files.append(f"{source}:{rel_path}")

            if skip_reasons:
                logger.info(
                    "Worker %s skip reasons: %s", worker_index + 1, dict(skip_reasons)
                )
            if error_reasons:
                logger.info(
                    "Worker %s exception types: %s",
                    worker_index + 1,
                    dict(error_reasons),
                )

            summary_msg = (
                f"Worker {worker_index + 1}/{workers} complete. Total assigned files: {total_files}, "
                f"Successful inserts: {total_successful_inserts}, duplicates skipped: {total_duplicates}, "
                f"Files with errors: {len(set(error_files))}"
            )
            logger.info(summary_msg)
            print(summary_msg)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        add_help=True, description="Populate daily values from raw_data into sec.db"
    )
    p.add_argument(
        "--db", default=DB_PATH, help="Path to SQLite DB (default: data/sec.db)"
    )
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        help=f"Total worker processes (default: {DEFAULT_WORKERS}).",
    )
    # Internal-only argument for the subprocess entrypoint.
    p.add_argument(
        INTERNAL_ARG_WORKER_INDEX,
        dest="_worker_index",
        type=int,
        default=None,
        help=argparse.SUPPRESS,
    )
    # Accept unknown args so `pytest` calling `m.main()` doesn't crash.
    args, _unknown = p.parse_known_args(argv)
    return args


def _split_into_chunks(
    files: list[tuple[str, str, str]], workers: int
) -> list[list[tuple[str, str, str]]]:
    """Split files into N chunks using the same deterministic round-robin as sharding."""
    if workers <= 1:
        return [files]
    chunks: list[list[tuple[str, str, str]]] = [[] for _ in range(workers)]
    for i, t in enumerate(files):
        chunks[i % workers].append(t)
    return chunks


def _run_worker_process(*, workers: int, worker_index: int, db_path: str) -> None:
    """Subprocess entrypoint."""
    _run(workers=workers, worker_index=worker_index, db_path=db_path)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    workers = _resolve_workers(args.workers)

    # If this is a spawned worker process, run only that shard.
    if getattr(args, "_worker_index", None) is not None:
        worker_index = int(args._worker_index)
        if worker_index < 0 or worker_index >= workers:
            raise SystemExit(
                f"Internal worker index must be in [0, {workers - 1}] (got {worker_index}; workers={workers})"
            )
        _run(workers=workers, worker_index=worker_index, db_path=args.db)
        return

    # Parent process: show a confirmation prompt before doing any work/spawning.
    try:
        summary = _summarize_run_setup(db_path=args.db, workers=workers)
        est = summary["est_per_worker"]
        est_str = (
            ", ".join(f"w{idx + 1}={cnt}" for idx, cnt in enumerate(est))
            if est
            else "(n/a)"
        )

        print("\npopulate_daily_values.py planned setup")
        print(f"- workers: {summary['workers']}")
        print(
            f"- files: total={summary['total_files']} skipped(already processed)={summary['skipped_files']} left_to_process={summary['files_left']}"
        )
        print(f"- estimated distribution per worker (files): {est_str}")

        if summary["files_left"] == 0:
            print("Nothing to do (all files appear already processed).")
            return

        if not _prompt_yes_no("Proceed with this setup?", default_no=True):
            print("Aborted.")
            return

    except Exception as e:
        # Do not block execution if the summary fails; just log and continue.
        logger.warning("Could not compute run summary for prompt: %s", e)
        if not _prompt_yes_no("Proceed without summary?", default_no=True):
            print("Aborted.")
            return

    if workers == 1:
        _run(workers=1, worker_index=0, db_path=args.db)
        return

    # Use 'spawn' for macOS compatibility and to avoid fork-related SQLite issues.
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        # Start method already set.
        pass

    logger.info("Starting populate_daily_values with %s workers", workers)

    procs: list[Process] = []
    for wi in range(workers):
        p = Process(
            target=_run_worker_process,
            kwargs={"workers": workers, "worker_index": wi, "db_path": args.db},
        )
        p.start()
        procs.append(p)

    exit_codes = []
    for p in procs:
        p.join()
        exit_codes.append(p.exitcode)

    bad = [c for c in exit_codes if c not in (0, None)]
    if bad:
        raise SystemExit(f"One or more workers exited non-zero: {exit_codes}")


if __name__ == "__main__":
    main()
