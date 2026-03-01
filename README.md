# Investor Guide — AI Agent Context Document

> **Created by:** GitHub Copilot  
> **Purpose:** Provides an AI agent (GitHub Copilot or any LLM-based tool) with complete, structured project context to confidently implement new features, refactor code, or answer questions without guessing.

---

## 1. Project Goal

A **data-collection and exploration tool** for public company data, starting with the **US SEC EDGAR** dataset. The core philosophy is:

- Collect **raw, unprocessed, unopinionated** data from official sources.
- Store it **incrementally** in a local SQLite database.
- Expose a **minimal Flask web UI** as a proof-of-concept for browsing the data.
- Keep the architecture open for **additional data sources** (GLEIF, IRS, EU registries, etc.) without schema changes.
- Drive development through **pytest** (unit + E2E with Playwright).

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.13 |
| Web framework | Flask |
| ORM / DB | SQLAlchemy + SQLite (`data/sec.db`) |
| Validation | Pydantic |
| Testing | pytest + pytest-playwright (Playwright for E2E) |
| Linting / formatting | black, isort, flake8, pylint |
| Config | `pyproject.toml` + `settings.py` + env vars |

---

## 3. Repository Layout

```
app.py                      # Flask app factory (create_app)
config.py                   # Config class + configure_logging shim
settings.py                 # Single source of truth for settings dict
db.py                       # SQLAlchemy engine, SessionLocal, Base
logging_utils.py            # Unified logging (UTC, per-file, daily rotation)
requirements.txt            # Runtime deps: flask, sqlalchemy, pydantic
requirements-dev.txt        # Dev/test deps: pytest, playwright, black, etc.
pyproject.toml              # black, isort, pytest, pylint, flake8 config

api/
  blueprint.py              # Top-level blueprint factory; registers all page BPs
  routes.py                 # Legacy route file (routes migrated to api/pages/*)
  api_v1/
    blueprint.py            # /api/v1 versioned blueprint (stub, ready to extend)
  jobs/
    manager.py              # Background job runner (PopulateDailyValuesJob)
  pages/
    home.py                 # GET /            → home page
    check_cik.py            # GET /check-cik   → CIK entity explorer
    daily_values.py         # GET /daily-values → time-series viewer
    db_check.py             # GET /db-check, /sql → raw DB inspector (feature-flagged)
  schemas/                  # Pydantic request/response schemas
  services/
    daily_values_service.py # Query helpers for daily_values page

data/
  sec.db                    # Live SQLite database

docs/
  RAW_DATA_SOURCES.md       # Curated list of free/legal data sources (US + global)
  sec_api_adoption_plan.md  # Prioritised roadmap for SEC API + multi-source expansion

models/
  __init__.py               # Imports Base; all models must register here
  entities.py               # Entity (id, canonical_uuid, cik)
  entity_identifiers.py     # External identifiers (scheme + value; unique per scheme)
  entity_metadata.py        # Company metadata (name, SIC, tickers, LEI, etc.)
  daily_values.py           # Core fact table (entity × date × value_name → value)
  dates.py                  # DateEntry (normalised date strings)
  units.py                  # Unit of measure (USD, shares, NA, etc.)
  value_names.py            # Metric/concept names (e.g. us-gaap.Assets)
  file_processing.py        # Tracks which raw JSON files have been ingested

modules/
  process_data.py           # Parses SEC companyfacts JSON → list of flat dicts
  load_to_db.py             # Stub (future: DB loading logic)

utils/
  populate_daily_values.py  # Main ingestion script (companyfacts + submissions JSON)
  populate_value_names.py   # Back-fills value_names table
  recreate_sqlite_db.py     # Drop + re-create SQLite schema
  migrate_sqlite_schema.py  # Safe ALTER TABLE helpers for incremental migrations
  migrate_value_names_table.py
  update_value_names_source.py
  db_ops.py                 # Generic DB helpers
  file_ops.py               # File system helpers
  cleanup_logs.py           # Log rotation / pruning
  time_utils.py             # UTC helpers, parse_ymd_date, utcnow
  value_parsing.py          # parse_primitive (text → int/float/str)

pytests/
  conftest.py               # Session fixtures: seeded_live_server, temp SQLite DB
  common.py                 # Helpers: create_empty_sqlite_db, patch_app_db, add_dicts
  test_*.py                 # Unit + integration + E2E tests

raw_data/
  companyfacts/             # SEC EDGAR companyfacts JSON files (one per CIK)
  submissions/              # SEC EDGAR submissions JSON files (one per CIK)

static/                     # CSS / JS assets
templates/                  # Jinja2 HTML templates
  base.html
  pages/                    # Page-level templates
  components/               # Shared partials
  errors/                   # 404, 500 pages

support/
  copy_files.py             # Utility scripts for raw data management
  load_to_db.py             # Support-level DB loader
  restart_watcher.py        # Dev-mode file-change watcher

test_data/                  # Static JSON fixtures for pytest
logs/                       # App + test log files (per-module, UTC, daily rotation)
tmp/                        # Runtime temp files (e.g. restart_requested flag)
```

---

## 4. Database Schema

All tables use `entities.id` (INTEGER PK) as the foreign key — **never** use `canonical_uuid` or `cik` as a join key.

```
entities
  id              INTEGER PK
  canonical_uuid  TEXT UNIQUE  ← stable UUID, auto-generated
  cik             TEXT         ← SEC CIK (nullable; not unique globally)

entity_identifiers            ← canonical identity resolution table
  id              INTEGER PK
  entity_id       FK → entities.id  ON DELETE CASCADE
  scheme          TEXT  (e.g. 'sec_cik', 'gleif_lei', 'gb_companies_house')
  value           TEXT  (normalised)
  country         TEXT  NULLABLE
  issuer          TEXT  NULLABLE
  UNIQUE (scheme, value)

entity_metadata               ← 1:1 with entities
  entity_id       FK → entities.id  (PK)
  company_name, sic, sic_description, state_of_incorporation,
  fiscal_year_end, filer_category, entity_type, website, phone,
  ein, lei, tickers, exchanges, investor_website, ...

dates
  id              INTEGER PK
  date            TEXT UNIQUE  (YYYY-MM-DD)

units
  id              INTEGER PK
  name            TEXT UNIQUE  (e.g. 'USD', 'shares', 'NA')

value_names
  id              INTEGER PK
  name            TEXT UNIQUE  (e.g. 'us-gaap.Assets')
  unit_id         FK → units.id  NULLABLE
  source          TEXT  (e.g. 'sec')
  added_on        DATETIME
  valid_until     DATETIME NULLABLE

daily_values                  ← core fact table (large, time-series)
  id              INTEGER PK
  entity_id       FK → entities.id
  date_id         FK → dates.id
  value_name_id   FK → value_names.id
  value           TEXT  (stored as text; parse with utils/value_parsing.py)
  UNIQUE (entity_id, date_id, value_name_id)

file_processing               ← incremental ingestion tracker
  id              INTEGER PK
  entity_id       FK → entities.id
  source_file     TEXT
  processed_at    DATETIME
  UNIQUE (entity_id, source_file)
```

### Key design rules
- `daily_values.value` is always stored as **TEXT**; use `parse_primitive()` from `utils/value_parsing.py` to cast at read time.
- New data sources are supported by adding rows with a new `value_names.source` (e.g. `'gleif'`) — **no schema changes needed**.
- Identity resolution always goes through `entity_identifiers (scheme, value)` — never match by `entities.cik` directly.

---

## 5. Data Ingestion Pipeline

```
raw_data/companyfacts/*.json  ──┐
raw_data/submissions/*.json   ──┤──► utils/populate_daily_values.py ──► SQLite (data/sec.db)
                                │        │
                                │        ├─ get_or_create_entity_by_identifier()
                                │        ├─ INSERT OR IGNORE into daily_values
                                │        └─ file_processing (dedup / incremental)
                                │
                                └── modules/process_data.py  (companyfacts JSON parser)
```

- SEC rate limit: **≤ 10 req/s**, always include `User-Agent: AppName your@email.com`.
- The ingestion job can be triggered from the **Admin UI** and runs as a background subprocess (`api/jobs/manager.py`).
- `file_processing` table ensures each file is processed only once (incremental, safe to re-run).

---

## 6. Flask Application

### Startup

```
create_app()  ←  app.py
  ├── app.config.from_pyfile("settings.py")
  ├── configure_app_logging()
  ├── slow-request middleware (SLOW_REQUEST_MS env var, default 250 ms)
  └── create_api_blueprint()
        ├── home_bp        GET /
        ├── check_cik_bp   GET /check-cik
        ├── daily_values_bp GET /daily-values
        ├── db_check_bp    GET /db-check, /sql  (ENABLE_DB_CHECK flag)
        └── api_v1_bp      /api/v1  (versioned REST, stub)
```

### Feature flags (env vars / settings.py)
| Flag | Default | Effect |
|---|---|---|
| `ENABLE_DB_CHECK` | `True` | Enables `/db-check` and `/sql` routes |
| `LOG_LEVEL` | `INFO` | App log verbosity |
| `SLOW_REQUEST_MS` | `250` | Log requests slower than N ms (set `0` to disable) |
| `INIT_DB_ON_STARTUP` | not set | If `0`, skips DB init (used in tests) |

---

## 7. Key UI Pages

| URL | Purpose |
|---|---|
| `/` | Home — choose CIK explorer or admin tools |
| `/check-cik` | Look up an entity by CIK; shows metadata + links to daily values |
| `/daily-values?entity_id=N` | Time-series viewer; filter by value_name and unit |
| `/db-check` or `/sql` | Raw DB table inspector (dev tool) |
| `/admin` | Trigger ingestion jobs, DB init/recreate |

---

## 8. Testing

```bash
# Run all tests
pytest -q

# Run a specific file
pytest -q pytests/test_populate_daily_values.py

# Run E2E (requires a running server + Playwright browsers installed)
pytest -q pytests/test_e2e_check_cik.py
```

### Test infrastructure
- **`conftest.py`** provides `seeded_live_server` fixture — a real HTTP server backed by a temporary in-memory SQLite DB, used for E2E/Playwright tests.
- **`common.py`** provides `create_empty_sqlite_db`, `patch_app_db`, `add_dicts` — used in unit/integration tests.
- Tests never touch `data/sec.db`; all test DBs are in `tmp_path`.
- Pytest config lives in `pyproject.toml` (`testpaths = ["pytests"]`).

---

## 9. Adding a New Feature — Agent Checklist

When implementing a new feature, follow this order:

1. **Model change?** → Edit `models/<name>.py`, register in `models/__init__.py`, add migration in `utils/migrate_sqlite_schema.py`.
2. **New ingestion source?** → Add a parser in `utils/` or `modules/`, use `get_or_create_entity_by_identifier()` for entity resolution, insert via `INSERT OR IGNORE` + `file_processing` for idempotency.
3. **New API endpoint?** → Create `api/pages/<name>.py` with a Blueprint, register it in `api/blueprint.py`.
4. **New REST endpoint?** → Add to `api/api_v1/blueprint.py` under `/api/v1`.
5. **New service logic?** → Put query helpers in `api/services/`.
6. **New template?** → Add to `templates/pages/` and extend `templates/base.html`.
7. **Tests first (TDD preferred)** → Add to `pytests/test_<name>.py`; use fixtures from `conftest.py` and `common.py`.
8. **Settings/flags?** → Add to `settings.py` and mirror in `config.py` `Config` class.

---

## 10. Planned / In-Progress Work

See `docs/sec_api_adoption_plan.md` for the full prioritised roadmap. Key next items:

- **Priority 1** — Harden entity identity: add `entity_relationships` table, add `confidence`/`added_at`/`last_seen_at` columns to `entity_identifiers`.
- **Priority 2** — Expand SEC ingestion: submissions JSON, text filings via EDGAR Archives.
- **Priority 3** — Non-US data sources: GLEIF (LEI), IRS 990, EU registries — enabled by `value_names.source` + `entity_identifiers.scheme` pivots.
- **Priority 4** — `/api/v1` REST endpoints (stub blueprint already in place).
- **Long term** — Replace SQLite with PostgreSQL for multi-user/production use.

See `docs/RAW_DATA_SOURCES.md` for the curated list of approved data sources.

---

## 11. Conventions & Constraints

- **Line length:** 100 characters (black + flake8).
- **Imports:** isort with black profile.
- **Python version:** 3.13.
- **Timestamps:** Always UTC. Use `utils/time_utils.utcnow()` or `utcnow_sa_default`.
- **No silent failures:** ingestion errors must be logged (not swallowed).
- **DB session pattern:** always use `try/finally: session.close()` or context managers.
- **Value storage:** store numeric values as TEXT in `daily_values.value`; cast with `parse_primitive()`.
- **Identity resolution:** never match by `entities.cik`; always use `entity_identifiers (scheme, value)`.
- **SEC rate limit:** ≤ 10 req/s; all HTTP clients must throttle and send a proper `User-Agent`.

---

## Raw data (`raw_data/`) and external files

This repo uses `raw_data/` as a **local cache** for externally sourced files (e.g., SEC EDGAR downloads). Contents of `raw_data/` are **not committed to git**.

### How to obtain / regenerate external files

- **SEC EDGAR (official, free):**
  - Primary source: https://www.sec.gov/edgar/sec-api-documentation
  - Bulk data landing page: https://www.sec.gov/dera/data/edgar-log-file-data-set
  - See `docs/RAW_DATA_SOURCES.md` for a curated list of raw data sources and links.

- **Using this project’s ingestion jobs/scripts:**
  - `jobs/sec_rss_poller.py` populates the database with new filings to fetch.
  - `jobs/sec_api_ingest.py` downloads filing documents into `raw_data/forms/`.
  - `utils/populate_daily_values.py` ingests `raw_data/companyfacts/` and `raw_data/submissions/` into SQLite.

Note: some SEC endpoints require a descriptive `SEC_EDGAR_USER_AGENT` and may enforce rate limits.
