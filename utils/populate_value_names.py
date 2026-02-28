import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import json  # noqa: E402
from datetime import date as _date  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.dialects.sqlite import insert as sqlite_insert  # noqa: E402

from models import Base  # noqa: E402
from models.entities import Entity  # noqa: E402
from models.dates import DateEntry  # noqa: E402
from models.units import Unit  # noqa: E402
from models.value_names import ValueName  # noqa: E402

# Ensure all tables are registered on Base.metadata
import models.daily_values  # noqa: F401,E402
import models.file_processing  # noqa: F401,E402

RAW_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "raw_data")
SUBMISSIONS_DIR = os.path.join(RAW_DATA_DIR, "submissions")
COMPANYFACTS_DIR = os.path.join(RAW_DATA_DIR, "companyfacts")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sec.db")

engine = create_engine(f"sqlite:///{DB_PATH}")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def _normalize_cik(raw) -> str | None:
    if raw is None:
        return None
    try:
        return str(int(raw)).zfill(10)
    except Exception:
        s = str(raw).strip()
        if not s:
            return None
        if s.startswith("CIK"):
            s = s[3:]
        digits = "".join(ch for ch in s if ch.isdigit())
        return digits.zfill(10) if digits else None


def _parse_ymd(s: str) -> _date | None:
    try:
        return _date.fromisoformat(s)
    except Exception:
        return None


def _get_or_create_entity(session, cik10: str, company_name: str | None = None) -> int:
    with session.no_autoflush:
        row = session.query(Entity).filter_by(cik=cik10).first()
    if row:
        if company_name and not row.company_name:
            row.company_name = company_name
            session.flush()
        return row.id

    row = Entity(cik=cik10, company_name=company_name)
    session.add(row)
    session.flush()
    return row.id


def _get_or_create_unit(session, name: str | None) -> int:
    unit_name = (name or "NA").strip() or "NA"
    with session.no_autoflush:
        row = session.query(Unit).filter_by(name=unit_name).first()
    if row:
        return row.id
    row = Unit(name=unit_name)
    session.add(row)
    session.flush()
    return row.id


def _get_or_create_date_entry(session, date_str: str) -> int | None:
    d = _parse_ymd(date_str)
    if not d:
        return None
    with session.no_autoflush:
        row = session.query(DateEntry).filter_by(date=d).first()
    if row:
        return row.id
    row = DateEntry(date=d)
    session.add(row)
    session.flush()
    return row.id


def _get_or_create_value_name(session, name: str, unit_id: int | None = None) -> int:
    with session.no_autoflush:
        row = session.query(ValueName).filter_by(name=name).first()
    if row:
        # backfill unit_id if model supports it and it's missing
        if unit_id and getattr(row, "unit_id", None) is None:
            try:
                row.unit_id = unit_id
                session.flush()
            except Exception:
                pass
        return row.id

    kwargs = {"name": name}
    # Only set unit_id if the column exists in the model
    if hasattr(ValueName, "unit_id"):
        kwargs["unit_id"] = unit_id
    if hasattr(ValueName, "source"):
        kwargs["source"] = "sec"

    row = ValueName(**kwargs)
    session.add(row)
    session.flush()
    return row.id


def _iter_json_files(dir_path: str):
    if not os.path.isdir(dir_path):
        return
    for fn in sorted(os.listdir(dir_path)):
        if fn.lower().endswith(".json"):
            yield os.path.join(dir_path, fn), fn


def _process_submissions(session) -> dict[str, int]:
    counts = {"files": 0, "entities": 0, "dates": 0, "units": 0, "value_names": 0}

    na_unit_id = _get_or_create_unit(session, "NA")

    for path, fn in _iter_json_files(SUBMISSIONS_DIR):
        counts["files"] += 1
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            continue

        cik10 = _normalize_cik(data.get("cik"))
        company_name = (
            data.get("entityName") or data.get("name") or data.get("companyName")
        )
        company_name = company_name.strip() if isinstance(company_name, str) else None
        if cik10:
            _get_or_create_entity(session, cik10, company_name=company_name)
            counts["entities"] += 1

        # recent payloads can be nested or flattened
        recent = None
        filings = data.get("filings")
        if isinstance(filings, dict):
            r = filings.get("recent")
            if isinstance(r, dict):
                recent = r
        if (
            recent is None
            and "filings" not in data
            and isinstance(data.get("filingDate"), list)
        ):
            recent = data

        if not isinstance(recent, dict):
            continue

        # insert value_names and any dates present
        for key, arr in recent.items():
            if key in ("filingDate", "reportDate"):
                continue
            _get_or_create_value_name(session, f"submissions.recent.{key}", na_unit_id)
            counts["value_names"] += 1

        for date_key in ("filingDate", "reportDate"):
            arr = recent.get(date_key)
            if isinstance(arr, list):
                for ds in arr:
                    if isinstance(ds, str) and _get_or_create_date_entry(session, ds):
                        counts["dates"] += 1

    counts["units"] += 1  # NA unit
    return counts


def _process_companyfacts(session) -> dict[str, int]:
    counts = {"files": 0, "entities": 0, "dates": 0, "units": 0, "value_names": 0}

    for path, fn in _iter_json_files(COMPANYFACTS_DIR):
        counts["files"] += 1
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            continue

        cik10 = _normalize_cik(data.get("cik"))
        company_name = (
            data.get("entityName") or data.get("name") or data.get("companyName")
        )
        company_name = company_name.strip() if isinstance(company_name, str) else None
        if cik10:
            _get_or_create_entity(session, cik10, company_name=company_name)
            counts["entities"] += 1

        facts = data.get("facts")
        if not isinstance(facts, dict):
            continue

        for namespace, metrics in facts.items():
            if not isinstance(metrics, dict):
                continue
            for metric, metric_obj in metrics.items():
                if not isinstance(metric_obj, dict):
                    continue
                units = metric_obj.get("units")
                if not isinstance(units, dict):
                    continue

                value_name = f"{namespace}.{metric}"

                for unit_name, points in units.items():
                    if not isinstance(points, list):
                        continue
                    unit_id = _get_or_create_unit(session, unit_name)
                    counts["units"] += 1
                    _get_or_create_value_name(session, value_name, unit_id)
                    counts["value_names"] += 1

                    for p in points:
                        if not isinstance(p, dict):
                            continue
                        end = p.get("end")
                        if isinstance(end, str) and _get_or_create_date_entry(
                            session, end
                        ):
                            counts["dates"] += 1

    return counts


def main() -> None:
    session = Session()
    try:
        # Use a single transaction for speed; data is idempotent (get-or-create).
        submissions_counts = _process_submissions(session)
        companyfacts_counts = _process_companyfacts(session)
        session.commit()

        print(
            "populate_value_names complete. "
            f"submissions(files={submissions_counts['files']}, entities~={submissions_counts['entities']}, "
            f"dates~={submissions_counts['dates']}, units~={submissions_counts['units']}, "
            f"value_names~={submissions_counts['value_names']}) | "
            f"companyfacts(files={companyfacts_counts['files']}, entities~={companyfacts_counts['entities']}, "
            f"dates~={companyfacts_counts['dates']}, units~={companyfacts_counts['units']}, "
            f"value_names~={companyfacts_counts['value_names']})"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
