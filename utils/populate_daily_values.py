import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import json  # noqa: E402
import logging  # noqa: E402
from datetime import datetime  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402
from time import perf_counter  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.dialects.sqlite import insert as sqlite_insert  # noqa: E402
from models import Base  # noqa: E402
from models.entities import Entity  # noqa: E402
from models.value_names import ValueName  # noqa: E402
from models.units import Unit  # noqa: E402
from models.dates import DateEntry  # noqa: E402
from models.daily_values import DailyValue  # noqa: E402

# Setup logging
# Keep a detailed log file for post-run investigation,
# while still surfacing warnings/errors in console.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_file_handler = logging.FileHandler("populate_daily_values.log")
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.WARNING)
_console_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))

if not logger.handlers:
    logger.addHandler(_file_handler)
    logger.addHandler(_console_handler)

# Previously we populated from raw_data/submissions.
# Companyfacts is where the numeric facts/metrics live.
COMPANYFACTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "raw_data", "companyfacts"
)
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
    with session.no_autoflush:
        entity = session.query(Entity).filter_by(cik=cik).first()
    if not entity:
        entity = Entity(cik=cik, company_name=company_name)
        session.add(entity)
        session.commit()
        return entity

    # backfill company_name if missing
    if company_name and not entity.company_name:
        entity.company_name = company_name
        session.commit()

    return entity


def get_or_create_unit(name: str | None):
    unit_name = (name or "NA").strip() or "NA"
    with session.no_autoflush:
        unit = session.query(Unit).filter_by(name=unit_name).first()
    if not unit:
        unit = Unit(name=unit_name)
        session.add(unit)
        session.commit()
    return unit


def get_or_create_value_name(name, unit_id: int | None = None):
    with session.no_autoflush:
        value_name = session.query(ValueName).filter_by(name=name).first()
    if not value_name:
        value_name = ValueName(
            name=name,
            unit_id=unit_id,
            source="sec",
            added_on=datetime.utcnow(),
        )
        session.add(value_name)
        session.commit()
        return value_name

    # backfill unit_id if missing
    if unit_id and getattr(value_name, "unit_id", None) is None:
        value_name.unit_id = unit_id
        session.commit()

    return value_name


def get_or_create_date_entry(date_str):
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception as e:
        logger.error(f"Invalid date format: {date_str} - {e}")
        return None
    with session.no_autoflush:
        date_entry = session.query(DateEntry).filter_by(date=date_obj).first()
    if not date_entry:
        date_entry = DateEntry(date=date_obj)
        session.add(date_entry)
        session.commit()
    return date_entry


def delete_all_daily_values():
    """One-time callable: Delete all data from the DailyValue table."""
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


def main():
    files = sorted([f for f in os.listdir(COMPANYFACTS_DIR) if f.endswith(".json")])
    total_files = len(files)
    error_files = []

    total_successful_inserts = 0
    total_duplicates = 0

    print(f"Starting processing of {total_files} files.")
    logger.info(f"Starting processing of {total_files} files.")

    skip_reasons = Counter()
    error_reasons = Counter()
    skip_reason_samples: dict[str, list[str]] = defaultdict(list)

    # caches
    entity_cache: dict[str, int] = {}
    value_name_cache: dict[tuple[str, int | None], int] = {}
    unit_cache: dict[str, int] = {}
    date_cache: dict[str, int] = {}

    totals = Counter()

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

    def infer_cik_from_filename(name: str) -> str | None:
        base = os.path.basename(name)
        if not base.startswith("CIK"):
            return None
        digits = []
        for ch in base[3:]:
            if ch.isdigit():
                digits.append(ch)
            else:
                break
        cik = "".join(digits)
        return cik or None

    def iter_fact_points(facts: dict):
        """Yield flattened fact points from a companyfacts payload.

        Produces tuples:
          (value_name, unit_name, end_date_str, raw_value)

        Value name reflects parent structures (namespace + metric) only.
        Unit is stored separately in `units` and referenced by `value_names.unit_id`.
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
                    # still emit a placeholder metric so we can log it as unprocessed
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

    # Ensure NA unit exists.
    get_unit_id_cached("NA")

    for idx, filename in enumerate(files, 1):
        t0 = perf_counter()
        if idx % 100 == 0:
            logger.info("Progress: %s/%s files", idx, total_files)

        print(f"Processing file {idx}/{total_files}: {filename}")
        logger.info(f"Processing file {idx}/{total_files}: {filename}")

        file_path = os.path.join(COMPANYFACTS_DIR, filename)

        inserts_planned = 0
        duplicates = 0

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                skip_reasons["non_dict_json"] += 1
                _sample("non_dict_json", filename)
                continue

            cik = data.get("cik")
            if not cik:
                cik = infer_cik_from_filename(filename)
                if cik:
                    skip_reasons["missing_cik_inferred_from_filename"] += 1
                else:
                    skip_reasons["missing_cik_and_cannot_infer"] += 1
                    _sample("missing_cik_and_cannot_infer", filename)
                    error_files.append(filename)
                    continue

            # normalize CIK (SEC often stores as int in JSON)
            try:
                cik = str(int(cik)).zfill(10)
            except Exception:
                cik = str(cik).zfill(10)

            company_name = data.get("entityName") or None
            entity_id = get_entity_id_cached(cik, company_name=company_name)

            facts = data.get("facts")
            if not isinstance(facts, dict) or not facts:
                # Do not silently skip: log full context for investigation.
                skip_reasons["missing_facts"] += 1
                _sample("missing_facts", filename)
                logger.warning(
                    "Unprocessed file %s: missing/empty facts. top_keys=%s cik=%s entityName=%s",
                    filename,
                    sorted(list(data.keys())) if isinstance(data, dict) else None,
                    cik,
                    company_name,
                )
                error_files.append(filename)
                continue

            # insert all points for this file in one transaction
            for value_name, unit_name, end_date, raw_val in iter_fact_points(facts):
                date_id = get_date_id_cached(end_date)
                if not date_id:
                    skip_reasons["invalid_date_format"] += 1
                    logger.warning(
                        "Invalid date in file %s: value_name=%s unit=%s end=%s",
                        filename,
                        value_name,
                        unit_name,
                        end_date,
                    )
                    continue

                unit_id = get_unit_id_cached(unit_name)
                vn_id = get_value_name_id_cached(value_name, unit_id)

                inserts_planned += 1
                inserted_ok = _insert_daily_value_ignore(
                    entity_id=entity_id,
                    date_id=date_id,
                    value_name_id=vn_id,
                    value=_safe_str(raw_val),
                )
                if not inserted_ok:
                    duplicates += 1

            # Commit once per file
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                error_reasons["IntegrityError"] += 1
            except Exception as e:
                session.rollback()
                error_reasons[type(e).__name__] += 1
                logger.error(
                    "Commit failed for file %s: %s", filename, e, exc_info=True
                )
                error_files.append(filename)
                continue

            inserted = max(inserts_planned - duplicates, 0)
            total_successful_inserts += inserted
            total_duplicates += duplicates

            totals["files_processed"] += 1
            totals["inserted"] += inserted
            totals["duplicates"] += duplicates

            logger.info(
                "Completed file %s: inserted=%s dup=%s elapsed=%.2fs",
                filename,
                inserted,
                duplicates,
                perf_counter() - t0,
            )

        except Exception as e:
            # Ensure the session is usable for the next file
            session.rollback()
            error_reasons[type(e).__name__] += 1
            logger.error(f"Error processing file {filename}: {e}", exc_info=True)
            error_files.append(filename)

    session.close()

    if skip_reasons:
        logger.info("Skip reasons summary: %s", dict(skip_reasons.most_common()))
        logger.info("Skip reason samples: %s", dict(skip_reason_samples))
    if error_reasons:
        logger.info("Exception types summary: %s", dict(error_reasons.most_common()))

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
