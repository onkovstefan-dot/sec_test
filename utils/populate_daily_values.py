import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import json
import logging
from datetime import datetime
from collections import Counter, defaultdict
from time import perf_counter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from models import Base
from models.entities import Entity
from models.value_names import ValueName
from models.dates import DateEntry
from models.daily_values import DailyValue
from models.daily_values_text import DailyValueText

# Setup logging
# Keep a detailed log file for post-run investigation, while still surfacing warnings/errors in console.
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

SUBMISSIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "raw_data", "submissions"
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


def get_or_create_entity(cik):
    entity = session.query(Entity).filter_by(cik=cik).first()
    if not entity:
        entity = Entity(cik=cik)
        session.add(entity)
        session.commit()
    return entity


def get_or_create_value_name(name):
    value_name = session.query(ValueName).filter_by(name=name).first()
    if not value_name:
        value_name = ValueName(name=name, source=1, added_on=datetime.utcnow())
        session.add(value_name)
        session.commit()
    return value_name


def get_or_create_date_entry(date_str):
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception as e:
        logger.error(f"Invalid date format: {date_str} - {e}")
        return None
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
            f"Deleted {num_deleted} rows from DailyValue table via delete_all_daily_values()."
        )
    except Exception as e:
        session.rollback()
        print(f"Error deleting DailyValue data: {e}")
        logger.error(f"Error deleting DailyValue data: {e}", exc_info=True)


def main():
    files = [f for f in os.listdir(SUBMISSIONS_DIR) if f.endswith(".json")]
    total_files = len(files)
    error_files = []
    # Overall counters (accurate based on attempted inserts + observed duplicates)
    total_successful_inserts_numeric = 0
    total_successful_inserts_text = 0
    total_duplicates_numeric = 0
    total_duplicates_text = 0
    print(f"Starting processing of {total_files} files.")
    logger.info(f"Starting processing of {total_files} files.")

    # Track high-level reasons to quickly spot repetitive failure modes.
    skip_reasons = Counter()
    error_reasons = Counter()

    # Keep small samples of filenames per reason for investigation.
    skip_reason_samples: dict[str, list[str]] = defaultdict(list)

    # Caches to cut DB roundtrips drastically.
    entity_cache: dict[str, int] = {}
    value_name_cache: dict[str, int] = {}
    date_cache: dict[str, int] = {}

    # Run totals for logging.
    totals = Counter()

    def _sample(reason: str, fname: str, limit: int = 10) -> None:
        if len(skip_reason_samples[reason]) < limit:
            skip_reason_samples[reason].append(fname)

    def get_entity_id_cached(cik: str) -> int:
        if cik in entity_cache:
            return entity_cache[cik]
        entity_id = get_or_create_entity(cik).id
        entity_cache[cik] = entity_id
        return entity_id

    def get_value_name_id_cached(name: str) -> int:
        if name in value_name_cache:
            return value_name_cache[name]
        vn_id = get_or_create_value_name(name).id
        value_name_cache[name] = vn_id
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
        """Infer a numeric CIK from common SEC filename patterns.

        Expected examples:
        - CIK0000750556-submissions-002.json
        - CIK0000750556.json
        """
        base = os.path.basename(name)
        if not base.startswith("CIK"):
            return None
        # Take chars after 'CIK' until first non-digit
        digits = []
        for ch in base[3:]:
            if ch.isdigit():
                digits.append(ch)
            else:
                break
        return "".join(digits) or None

    for idx, filename in enumerate(files, 1):
        t0 = perf_counter()
        if idx % 1000 == 0:
            logger.info("Progress: %s/%s files", idx, total_files)
        print(f"Processing file {idx}/{total_files}: {filename}")
        logger.info(f"Processing file {idx}/{total_files}: {filename}")
        file_path = os.path.join(SUBMISSIONS_DIR, filename)
        # Per-file counters
        inserts_planned_numeric = 0
        inserts_planned_text = 0
        successful_inserts_numeric = 0  # only used in row-wise fallback
        successful_inserts_text = 0  # only used in row-wise fallback
        duplicates_numeric = 0
        duplicates_text = 0
        non_numeric_count = 0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # --- Schema routing (Option B): support multiple source shapes ---
            schema = "unknown"
            recent = None
            cik = None

            if isinstance(data, dict) and isinstance(data.get("filings"), dict):
                filings = data.get("filings", {})
                if isinstance(filings.get("recent"), dict) and filings.get("recent"):
                    schema = "full_submissions"
                    recent = filings.get("recent")
                    cik = data.get("cik")

            if recent is None and isinstance(data, dict):
                # flattened recent payload: top-level arrays like accessionNumber/filingDate/form...
                if (
                    "filings" not in data
                    and "accessionNumber" in data
                    and "filingDate" in data
                ):
                    schema = "flattened_recent"
                    recent = data
                    cik = data.get("cik")

            if recent is None:
                skip_reasons["unknown_schema"] += 1
                _sample("unknown_schema", filename)
                logger.warning(
                    "Skipping file %s: unknown schema. top_keys=%s",
                    filename,
                    sorted(list(data.keys()))[:25] if isinstance(data, dict) else None,
                )
                error_files.append(filename)
                continue

            # CIK resolution
            if not cik:
                inferred_cik = infer_cik_from_filename(filename)
                if inferred_cik:
                    logger.info(
                        "CIK missing in %s (schema=%s). Using inferred CIK %s from filename.",
                        filename,
                        schema,
                        inferred_cik,
                    )
                    cik = inferred_cik
                    skip_reasons["missing_cik_inferred_from_filename"] += 1
                else:
                    sample_content = str(data)[:500]
                    logger.error(
                        "Missing CIK in file %s (schema=%s) and could not infer from filename. Sample content: %s",
                        filename,
                        schema,
                        sample_content,
                    )
                    skip_reasons["missing_cik_and_cannot_infer"] += 1
                    _sample("missing_cik_and_cannot_infer", filename)
                    error_files.append(filename)
                    continue

            entity_id = get_entity_id_cached(cik)

            if not isinstance(recent, dict) or not recent:
                skip_reasons["missing_recent"] += 1
                _sample("missing_recent", filename)
                logger.warning(
                    "Skipping file %s (schema=%s): recent object missing/empty.",
                    filename,
                    schema,
                )
                error_files.append(filename)
                continue

            logger.info(
                "File %s detected schema=%s keys=%s", filename, schema, len(recent)
            )

            # Loop over all value names in recent
            for value_name in recent.keys():
                vn_id = get_value_name_id_cached(value_name)
                values = recent.get(value_name, [])
                if not isinstance(values, list):
                    skip_reasons["recent_value_not_list"] += 1
                    logger.warning(
                        "Skipping value_name %s in file %s: expected list, got %s",
                        value_name,
                        filename,
                        type(values).__name__,
                    )
                    continue
                # Find the corresponding date array
                if value_name == "filingDate":
                    date_values = values
                elif value_name == "reportDate":
                    date_values = values
                else:
                    # Use filingDate if available, else skip
                    date_values = recent.get("filingDate", [])
                # Loop over values and dates
                for idx_val, val in enumerate(values):
                    # Try to get date for this value
                    date_str = None
                    if value_name in ["filingDate", "reportDate"]:
                        date_str = val
                    elif "filingDate" in recent and idx_val < len(recent["filingDate"]):
                        date_str = recent["filingDate"][idx_val]
                    elif "reportDate" in recent and idx_val < len(recent["reportDate"]):
                        date_str = recent["reportDate"][idx_val]
                    if not date_str:
                        skip_reasons["missing_date_for_value"] += 1
                        continue
                    date_id = get_date_id_cached(date_str)
                    if not date_id:
                        skip_reasons["invalid_date_format"] += 1
                        continue

                    # Store value: numeric -> DailyValue, else -> DailyValueText
                    try:
                        value_float = float(val)
                        is_numeric = True
                    except (ValueError, TypeError):
                        is_numeric = False
                        non_numeric_count += 1

                    if is_numeric:
                        inserts_planned_numeric += 1
                        session.add(
                            DailyValue(
                                entity_id=entity_id,
                                value_name_id=vn_id,
                                date_id=date_id,
                                value=value_float,
                            )
                        )
                    else:
                        inserts_planned_text += 1
                        session.add(
                            DailyValueText(
                                entity_id=entity_id,
                                value_name_id=vn_id,
                                date_id=date_id,
                                value_text=_safe_str(val),
                            )
                        )

                # Batch flush per value_name to surface constraints earlier without committing per row.
                try:
                    session.flush()
                except IntegrityError as e:
                    session.rollback()
                    # Duplicates are expected (same entity/value/date). Count and continue.
                    skip_reasons["duplicate_unique_constraint"] += 1
                    error_reasons["IntegrityError"] += 1
                    # Keep rolling: we don't know which record collided in the batch, so fallback to row-wise insert.
                    # This is slower, but only for problematic sets.
                    for idx_val, val in enumerate(values):
                        date_str = None
                        if value_name in ["filingDate", "reportDate"]:
                            date_str = val
                        elif "filingDate" in recent and idx_val < len(
                            recent["filingDate"]
                        ):
                            date_str = recent["filingDate"][idx_val]
                        elif "reportDate" in recent and idx_val < len(
                            recent["reportDate"]
                        ):
                            date_str = recent["reportDate"][idx_val]
                        if not date_str:
                            continue
                        date_id = get_date_id_cached(date_str)
                        if not date_id:
                            continue
                        try:
                            value_float = float(val)
                            is_numeric = True
                        except (ValueError, TypeError):
                            is_numeric = False
                        if is_numeric:
                            inserts_planned_numeric += 1
                        else:
                            inserts_planned_text += 1
                        try:
                            if is_numeric:
                                session.add(
                                    DailyValue(
                                        entity_id=entity_id,
                                        value_name_id=vn_id,
                                        date_id=date_id,
                                        value=value_float,
                                    )
                                )
                                session.flush()
                                successful_inserts_numeric += 1
                            else:
                                session.add(
                                    DailyValueText(
                                        entity_id=entity_id,
                                        value_name_id=vn_id,
                                        date_id=date_id,
                                        value_text=_safe_str(val),
                                    )
                                )
                                session.flush()
                                successful_inserts_text += 1
                        except IntegrityError:
                            session.rollback()
                            if is_numeric:
                                duplicates_numeric += 1
                            else:
                                duplicates_text += 1
                        except Exception as e2:
                            session.rollback()
                            error_reasons[type(e2).__name__] += 1
                            logger.error(
                                "Row insert failed file=%s value_name=%s date=%s: %s",
                                filename,
                                value_name,
                                date_str,
                                e2,
                                exc_info=True,
                            )

            # Commit once per file (major speed improvement)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                # If we hit integrity errors at commit time, count and proceed.
                error_reasons["IntegrityError"] += 1
            except Exception as e:
                session.rollback()
                error_reasons[type(e).__name__] += 1
                logger.error(
                    "Commit failed for file %s: %s", filename, e, exc_info=True
                )
                error_files.append(filename)
                continue

            # Derive successful insert counts (planned - duplicates observed in row-wise fallback)
            file_inserted_numeric = max(inserts_planned_numeric - duplicates_numeric, 0)
            file_inserted_text = max(inserts_planned_text - duplicates_text, 0)

            total_successful_inserts_numeric += file_inserted_numeric
            total_successful_inserts_text += file_inserted_text
            total_duplicates_numeric += duplicates_numeric
            total_duplicates_text += duplicates_text

            totals["files_processed"] += 1
            totals["inserted_numeric"] += file_inserted_numeric
            totals["inserted_text"] += file_inserted_text
            totals["duplicates_numeric"] += duplicates_numeric
            totals["duplicates_text"] += duplicates_text

            logger.info(
                "Completed file %s schema=%s: inserted_num=%s inserted_text=%s non_numeric=%s dup_num=%s dup_text=%s elapsed=%.2fs",
                filename,
                schema,
                file_inserted_numeric,
                file_inserted_text,
                non_numeric_count,
                duplicates_numeric,
                duplicates_text,
                perf_counter() - t0,
            )
        except Exception as e:
            error_reasons[type(e).__name__] += 1
            logger.error(f"Error processing file {filename}: {e}", exc_info=True)
            error_files.append(filename)

    session.close()

    # Log a compact breakdown of what happened to speed up follow-up investigation.
    if skip_reasons:
        logger.info("Skip reasons summary: %s", dict(skip_reasons.most_common()))
        logger.info("Skip reason samples: %s", dict(skip_reason_samples))
    if error_reasons:
        logger.info("Exception types summary: %s", dict(error_reasons.most_common()))

    # Summary logging
    inserted_total = total_successful_inserts_numeric + total_successful_inserts_text
    summary_msg = (
        f"Processing complete. Total files: {total_files}, "
        f"Total successful inserts: {inserted_total} "
        f"(numeric={total_successful_inserts_numeric}, text={total_successful_inserts_text}), "
        f"Total duplicates skipped (numeric={total_duplicates_numeric}, text={total_duplicates_text}), "
        f"Files with errors: {len(set(error_files))}"
    )
    print(summary_msg)
    logger.info(summary_msg)
    if error_files:
        logger.error(f"Files with errors: {set(error_files)}")


if __name__ == "__main__":
    main()
