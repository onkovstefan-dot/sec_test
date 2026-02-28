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

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import json  # noqa: E402
import logging  # noqa: E402
from datetime import datetime  # noqa: E402
from utils.time_utils import utcnow, parse_ymd_date  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402
from time import perf_counter  # noqa: E402
import threading  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from functools import wraps  # noqa: E402
from sqlalchemy import create_engine, func  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.dialects.sqlite import insert as sqlite_insert  # noqa: E402
from models import Base  # noqa: E402
from models.entities import Entity  # noqa: E402
from models.value_names import ValueName  # noqa: E402
from models.units import Unit  # noqa: E402
from models.dates import DateEntry  # noqa: E402
from models.daily_values import DailyValue  # noqa: E402
from models.file_processing import FileProcessing  # noqa: E402
from logging_utils import get_logger  # noqa: E402


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


# Setup logging (shared app logger; per-file logs in ./logs/)
logger = get_logger(__name__)

# Previously we populated from raw_data/submissions.
# Companyfacts is where the numeric facts/metrics live.
RAW_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "raw_data")
COMPANYFACTS_DIR = os.path.join(RAW_DATA_DIR, "companyfacts")
SUBMISSIONS_DIR = os.path.join(RAW_DATA_DIR, "submissions")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sec.db")
engine = create_engine(f"sqlite:///{DB_PATH}")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()


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


def _insert_daily_values_ignore_bulk(rows: list[dict]) -> int:
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
        inserted += int(getattr(res, "rowcount", 0) or 0)

    return inserted


# Keep the single-row helper for potential future/diagnostics use.
def _insert_daily_value_ignore(
    entity_id: int, date_id: int, value_name_id: int, value: str
) -> bool:
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


def get_or_create_entity(cik, company_name: str | None = None):
    """Get an `Entity` by CIK or create it.

    Optimized: avoids committing inside helper; caller controls transaction.
    """
    with session.no_autoflush:
        entity = session.query(Entity).filter_by(cik=cik).first()
    if not entity:
        entity = Entity(cik=cik, company_name=company_name)
        session.add(entity)
        session.flush()  # assign PK without committing
        return entity

    # backfill company_name if missing
    if company_name and not entity.company_name:
        entity.company_name = company_name
        session.flush()

    return entity


def get_or_create_unit(name: str | None):
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


def get_or_create_value_name(name, unit_id: int | None = None):
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


def get_or_create_date_entry(date_str):
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


def delete_all_daily_values():
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


def extract_entity_identity(data: dict, filename: str) -> tuple[str | None, str | None]:
    """Extract (cik10, company_name) from payload, falling back to filename."""
    cik = _normalize_cik(data.get("cik"))
    if not cik:
        inferred = infer_cik_from_filename(filename)
        cik = _normalize_cik(inferred)
    company_name = data.get("entityName") or data.get("name") or data.get("companyName")
    company_name = company_name.strip() if isinstance(company_name, str) else None
    return cik, company_name


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
) -> tuple[int, int]:
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

    inserted = _insert_daily_values_ignore_bulk(rows)
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
) -> tuple[str, int, int, str | None]:
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

    inserted = _insert_daily_values_ignore_bulk(rows)
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


def _mark_file_processed(entity_id: int, source_file: str) -> None:
    """Insert a processed marker row (idempotent)."""
    stmt = (
        sqlite_insert(FileProcessing)
        .values(entity_id=entity_id, source_file=source_file)
        .prefix_with("OR IGNORE")
    )
    session.execute(stmt)


def _load_processed_file_keys() -> set[str]:
    """Load processed file keys into memory for fast skipping."""
    try:
        rows = session.query(FileProcessing.source_file).all()
        return {r[0] for r in rows}
    except Exception:
        # If table doesn't exist for some reason, Base.metadata.create_all should have
        # created it; but play safe.
        return set()


@timed("main", logger_obj=logger)
def main():
    """Entry point: discover JSON files, process them, and write summary logs."""
    with timed_block("populate_daily_values total", logger_obj=logger):
        # Discover all JSON files under raw_data recursively.
        files = discover_json_files(RAW_DATA_DIR)

        # Incremental run support: skip files already recorded as processed.
        processed = _load_processed_file_keys()

        total_files = len(files)
        error_files: list[str] = []

        total_successful_inserts = 0
        total_duplicates = 0

        # Explain upfront whether we'll skip already-processed files.
        if processed:
            print(
                f"Starting processing of {total_files} files. Incremental mode: "
                f"will skip {len(processed)} previously-processed files."
            )
        else:
            print(
                f"Starting processing of {total_files} files. No previously-processed files to skip."
            )
        logger.info(f"Starting processing of {total_files} files.")

        if processed:
            logger.info(
                "Incremental mode: %s files already processed; will skip.",
                len(processed),
            )

        skip_reasons = Counter()
        error_reasons = Counter()
        skip_reason_samples: dict[str, list[str]] = defaultdict(list)

        # caches
        entity_cache: dict[str, int] = {}
        value_name_cache: dict[tuple[str, int | None], int] = {}
        unit_cache: dict[str, int] = {}
        date_cache: dict[str, int] = {}

        totals = Counter()

        # Reduce noisy per-file info logs; keep progress and errors.
        verbose_per_file = False

        def _sample(reason: str, fname: str, limit: int = 10) -> None:
            if len(skip_reason_samples[reason]) < limit:
                skip_reason_samples[reason].append(fname)

        def get_entity_id_cached(cik: str, company_name: str | None = None) -> int:
            key = cik
            if key in entity_cache:
                # still backfill name via DB if needed
                if company_name:
                    get_or_create_entity(cik, company_name)
                return entity_cache[key]
            entity_id = get_or_create_entity(cik, company_name=company_name).id
            entity_cache[key] = entity_id
            return entity_id

        def get_unit_id_cached(unit_name: str | None) -> int:
            key = (unit_name or "NA").strip() or "NA"
            if key in unit_cache:
                return unit_cache[key]
            unit_id = get_or_create_unit(key).id
            unit_cache[key] = unit_id
            return unit_id

        def get_value_name_id_cached(name: str, unit_id: int | None) -> int:
            key = (name, unit_id)
            if key in value_name_cache:
                return value_name_cache[key]
            vn_id = get_or_create_value_name(name, unit_id=unit_id).id
            value_name_cache[key] = vn_id
            return vn_id

        def get_date_id_cached(date_str: str) -> int | None:
            if date_str in date_cache:
                return date_cache[date_str]
            date_entry = get_or_create_date_entry(date_str)
            if not date_entry:
                return None
            date_cache[date_str] = date_entry.id
            return date_entry.id

        # Ensure NA unit exists.
        get_unit_id_cached("NA")

        for idx, (source, file_path, filename) in enumerate(files, 1):
            t0 = perf_counter()

            rel_path = os.path.relpath(file_path, RAW_DATA_DIR)
            file_key = _source_file_key(source, rel_path)
            if file_key in processed:
                continue

            if idx % 100 == 0:
                logger.info("Progress: %s/%s files", idx, total_files)
                print(f"Progress: {idx}/{total_files} files")

            if verbose_per_file:
                print(f"Processing file {idx}/{total_files}: [{source}] {rel_path}")
                logger.info(
                    f"Processing file {idx}/{total_files}: [{source}] {rel_path}"
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

                cik, company_name = extract_entity_identity(data, filename)
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

                entity_id = get_entity_id_cached(cik, company_name=company_name)

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

                # Mark file processed and commit once per file (data + marker row)
                _mark_file_processed(entity_id=entity_id, source_file=file_key)

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

                # update in-memory processed set so we don't redo it in the same run
                processed.add(file_key)

                inserted = max(inserts_planned - duplicates, 0)
                total_successful_inserts += inserted
                total_duplicates += duplicates

                totals["files_processed"] += 1
                totals["inserted"] += inserted
                totals["duplicates"] += duplicates

                logger.info(
                    "Completed file %s source=%s: inserted=%s dup=%s elapsed=%.2fs",
                    rel_path,
                    source,
                    inserted,
                    duplicates,
                    perf_counter() - t0,
                )

            except Exception as e:
                session.rollback()
                error_reasons[type(e).__name__] += 1
                logger.error(f"Error processing file {rel_path}: {e}", exc_info=True)
                error_files.append(f"{source}:{rel_path}")

        session.close()

        if skip_reasons:
            logger.info("Skip reasons summary: %s", dict(skip_reasons.most_common()))
            logger.info("Skip reason samples: %s", dict(skip_reason_samples))
        if error_reasons:
            logger.info(
                "Exception types summary: %s", dict(error_reasons.most_common())
            )

        summary_msg = (
            f"Processing complete. Total files: {total_files}, "
            f"Total successful inserts: {total_successful_inserts}, "
            f"Total duplicates skipped: {total_duplicates}, "
            f"Files with errors: {len(set(error_files))}"
        )
        print(summary_msg)
        logger.info(summary_msg)
        if error_files:
            logger.error(f"Files with errors: {set(error_files)}")


if __name__ == "__main__":
    main()
