# SEC API Adoption Plan

This document outlines the **priority-ordered** plan for growing the data pipeline and
SEC EDGAR integration. It is grounded in the **actual current codebase** so every
step refers to real files and models.

---

## How to Execute This Plan With Fresh AI-Agent Sessions (Mandatory)

This roadmap is intended to be executed as a sequence of **separate, consecutive, fresh sessions** with AI coding agents. Each session assumes the agent starts with **no memory**. To avoid context loss, each session has:

- a **Session Goal**
- an explicit **Read-First context pack** (must be opened in that session)
- concrete **Tasks**
- **Exit criteria** (what must be true before moving on)
- a **Handoff note** (what to paste into the next fresh session)

### Global agent rules (apply in every session)

These rules are consistent with the architecture described in `README.md`:

- **Project context source of truth:** `README.md` (especially: repo layout, DB schema rules, ingestion flow, and testing approach).
- **Primary FK for fact tables:** `entities.id` — never expose `canonical_uuid` or CIK directly as a join key.
- **Identity resolution:** always go through `entity_identifiers (scheme, value)` — never match by `entities.cik` directly.
- **Numeric data:** ingest from `companyfacts` JSON (facts/metrics).
- **Index / filings list:** ingest from `submissions` JSON.
- **Text / HTML filings:** construct `Archives/edgar/data/...` URLs from submissions data.
- **Rate limiting:** ≤ 10 requests/second to SEC EDGAR (target 9 req/s). All HTTP clients must throttle.
- **Headers:** every SEC request must include `User-Agent` (see `README.md` + `settings.py` notes).
- **Testing-first:** implement or adjust tests in `pytests/` for every new model/migration/normalization change (see `README.md` testing section).

### Session hygiene and context handoff protocol

In each session:

1. **Read first**:
   - `README.md` (project goal, layout, schema, ingestion flow)
   - This file: `docs/sec_api_adoption_plan.md`
   - Any files explicitly listed under that session’s “Read-First context pack”
2. **Confirm invariants before coding**:
   - models register in `models/__init__.py` (per `README.md`)
   - migrations are idempotent in `utils/migrate_sqlite_schema.py`
   - ingestion changes remain incremental and deduplicated via `models/file_processing.py`
3. **After coding**:
   - run unit/integration tests (pytest)
   - run a quick local sanity check against `data/sec.db` (or a temp test DB) without breaking existing routes.

### Intermediate checkpoints (do not skip)

Between sessions, insist on these checkpoints to keep execution robust:

- **Checkpoint A — Schema sanity:** new tables exist; columns added with defaults; constraints are correct.
- **Checkpoint B — Ingestion idempotence:** re-running ingestion does not duplicate rows.
- **Checkpoint C — API/Jobs stability:** the Flask app still starts; background job manager still works.
- **Checkpoint D — Tests green:** pytest suite passes (or failures are explicitly justified and fixed in the same session).

---

## Core Architectural Guidelines & Constraints

(These are restated here because fresh sessions should treat them as always-present invariants. They are also reflected in `README.md` “Database Schema” and “Data Ingestion Pipeline” sections.)

- **Primary FK for fact tables:** `entities.id` — never expose `canonical_uuid` or CIK directly as a join key.
- **Identity resolution:** always go through `entity_identifiers (scheme, value)` — never match by `entities.cik` directly.
- **Numeric data:** ingest from `companyfacts` JSON (facts/metrics).
- **Index / filings list:** ingest from `submissions` JSON.
- **Text / HTML filings:** construct `Archives/edgar/data/...` URLs from submissions data.
- **Rate limiting:** ≤ 10 requests/second to SEC EDGAR. All HTTP clients must throttle.
- **Headers:** every SEC request must include `User-Agent: AppName your@email.com`.
- **Multi-source design:** `entity_identifiers.scheme` + `value_names.source` are the two pivots that let the same tables hold data from SEC, GLEIF, IRS, ESMA, etc. without schema changes.

---

## Session 0 — Baseline Orientation & Inventory (fresh session)

**Session Goal:** Ensure the agent understands the repo and can safely modify schema + ingestion without breaking invariants.

**Read-First context pack:**
- `README.md` (required)
- `db.py`, `settings.py`
- `models/__init__.py`, `models/entities.py`, `models/entity_identifiers.py`, `models/file_processing.py`
- `utils/migrate_sqlite_schema.py`, `utils/populate_daily_values.py`
- `api/jobs/manager.py`

**Tasks:**
1. Identify how models are registered and how `Base` is imported (see `README.md` “Repository Layout”).
2. Confirm the migration approach used by `utils/migrate_sqlite_schema.py` is idempotent and safe.
3. Confirm how `FileProcessing` enforces ingestion deduplication (per `README.md` “Data Ingestion Pipeline”).
4. Write down the exact test entry points used in this repo (pytest config in `pyproject.toml`, fixtures in `pytests/conftest.py`).

**Exit criteria:**
- A short note listing: model registration steps, migration pattern, ingestion dedupe approach, and where to add tests.

**Handoff note to next session:**
- Paste the inventory note + any discovered pitfalls (e.g., naming conventions, existing helpers like `utcnow` in `utils/time_utils.py`).

---

## Session 1 — Priority 1A: Add Entity Relationships Model (fresh session)

> **Goal:** Make `entities` + `entity_identifiers` the single authoritative identity layer before any new data source is added.

### Current state (per codebase + `README.md`)
- `entities` has `id` (PK) and `canonical_uuid` (stable UUID string, generated on insert).
- `entity_identifiers` has `(scheme, value)` unique constraint and normalization helpers in `utils/populate_daily_values.py` (`_scheme_alias`, `_normalize_identifier_value`, `get_or_create_entity_by_identifier`).
- **Gap:** no model for parent/subsidiary/branch relationship edges.

### Tasks

1. **Add `entity_relationships` table** (`models/entity_relationships.py`)

   Schema:

   ```
   id                  INTEGER  PK autoincrement
   parent_entity_id    INTEGER  FK entities.id  ON DELETE CASCADE
   child_entity_id     INTEGER  FK entities.id  ON DELETE CASCADE
   relationship_type   TEXT     NOT NULL   -- 'subsidiary', 'branch', 'parent', 'merged_into', 'regional', 'same_as', etc.
   ownership_pct       REAL     NULLABLE   -- e.g. 100.0 for wholly-owned subsidiary
   effective_from      DATE     NULLABLE
   effective_to        DATE     NULLABLE
   source              TEXT     NULLABLE   -- 'sec_submissions', 'gleif_l2', 'manual', etc.
   UNIQUE (parent_entity_id, child_entity_id, relationship_type)
   ```

   Requirements:
   - Register in `models/__init__.py` (required per `README.md`).
   - Add SQLAlchemy relationships if appropriate, but keep it minimal and consistent with existing models.

2. **Deterministic child canonical UUID derivation (design + utility function)**

   The plan requirement is:

   `uuid5(NAMESPACE_URL, f"{parent_canonical_uuid}:{relationship_type}:{child_scheme}:{child_value}")`

   Intermediate steps:
   - Decide where the UUID derivation function lives (recommend: `utils/entity_identity.py` or similar small module).
   - Add tests proving determinism.
   - Important: do **not** change how `entities.canonical_uuid` is created globally unless explicitly required. Keep this derivation as a helper used when creating a *new* child entity based on relationship knowledge.

3. **Unit tests** in `pytests/`:
   - determinism: same inputs produce same UUID
   - collision resistance sanity: different relationship_type or identifier changes UUID

### Exit criteria
- Model exists, is registered, migrations/schema creation path is updated (however this repo handles new model creation).
- Tests pass.

### Handoff note to next session
- File list changed + how the relationship model is created (migration vs recreate script) + the final UUID derivation function signature.

---

## Session 2 — Priority 1B: Harden `entity_identifiers` Columns (fresh session)

**Session Goal:** Add confidence/timestamps so identifier mappings can be audited over time.

**Read-First context pack:**
- `README.md` “Database Schema” (entity_identifiers section)
- `models/entity_identifiers.py`
- `utils/migrate_sqlite_schema.py`
- `utils/time_utils.py` (for `utcnow`)

**Tasks:**

1. Add 3 columns to `entity_identifiers` via `utils/migrate_sqlite_schema.py`:

   | Column | Type | Default | Purpose |
   |--------|------|---------|---------|
   | `confidence` | TEXT | `'authoritative'` | `'authoritative'`, `'inferred'`, `'manual'` |
   | `added_at` | DATETIME | `utcnow` | first recorded |
   | `last_seen_at` | DATETIME | NULL | last confirmed |

2. Update the SQLAlchemy model `models/entity_identifiers.py` accordingly.

3. Intermediate steps to keep it robust:
   - If existing rows exist, ensure the migration backfills safe defaults.
   - Ensure inserts in `get_or_create_entity_by_identifier()` set `added_at` (and optionally `last_seen_at`) in a consistent way.

4. Tests:
   - migration test: schema contains the columns after migration
   - insertion test: new identifier rows get defaults

**Exit criteria:**
- DB migration is idempotent.
- All tests green.

**Handoff note:**
- Provide the migration function names added and whether any call site changes were needed.

---

## Session 3 — Priority 1C: Extend Scheme Normalization (fresh session)

**Session Goal:** Support planned identifier schemes with strict normalization rules.

**Read-First context pack:**
- `README.md` schema rule: identity resolution must go through `entity_identifiers`
- `utils/populate_daily_values.py` (`_scheme_alias`, `_normalize_identifier_value`, `get_or_create_entity_by_identifier`)

**Tasks:**

1. Extend `_scheme_alias` / `_normalize_identifier_value` in `utils/populate_daily_values.py` for:

   | Scheme | Normalization rule |
   |---|---|
   | `gleif_lei` | Uppercase, exactly 20 alpha-num chars |
   | `isin` | Uppercase, exactly 12 chars |
   | `gb_companies_house` | Zero-pad to 8 digits |
   | `fr_siren` | 9 digits only |
   | `eu_vat` | Strip spaces, uppercase |
   | `ticker_exchange` | Format `{TICKER}:{MIC}` uppercase |

2. Intermediate steps:
   - For each scheme, define: (a) accepted raw inputs, (b) normalized output, (c) error behavior (raise vs return None) and keep it consistent across schemes.
   - Add a small table-driven test suite for normalization.

3. Tests:
   - round-trip: raw inputs normalize to expected outputs
   - invalid formats are handled deterministically (assert raised error or returned None)

**Exit criteria:**
- Normalization is deterministic and covered.

**Handoff note:**
- Paste the normalization table used in tests + any edge cases found in real SEC data.

---

## Session 4 — Priority 1D: Integrity Behavior for Conflicting Identifiers (fresh session)

**Session Goal:** Ensure `get_or_create_entity_by_identifier` behaves safely when two sources claim the same identifier.

**Read-First context pack:**
- `README.md` “Key design rules” (identity resolution)
- `utils/populate_daily_values.py` (`get_or_create_entity_by_identifier`)
- `models/entity_identifiers.py`

**Tasks:**
- Add/adjust logic so that if an identifier `(scheme, value)` already exists for a different `entity_id`, an `IntegrityError` (or explicit custom exception) is raised.
- Add tests that simulate conflicting claims.

**Exit criteria:**
- Test proves conflicts are caught.

**Handoff note:**
- Provide the exact exception behavior and message to look for.

---

## Session 5 — Priority 2A: Add `sec_filings` / `sec_tickers` Models (fresh session)

**Session Goal:** Persist submissions “recent filings” and tickers into structured tables.

**Read-First context pack:**
- `README.md` repository layout: models + migrations + ingestion
- `utils/populate_daily_values.py` submissions parsing
- `models/entity_metadata.py` (tickers/exchanges fields)

**Tasks:**

1. Add `models/sec_filings.py`:

   ```
   id                INTEGER  PK autoincrement
   entity_id         INTEGER  FK entities.id  ON DELETE CASCADE
   accession_number  TEXT     NOT NULL        -- normalized: dashes removed
   form_type         TEXT     NOT NULL
   filing_date       DATE     NULLABLE
   report_date       DATE     NULLABLE
   primary_document  TEXT     NULLABLE
   index_url         TEXT     NULLABLE
   document_url      TEXT     NULLABLE
   full_text_url     TEXT     NULLABLE
   fetched_at        DATETIME NULLABLE
   fetch_status      TEXT     DEFAULT 'pending'
   source            TEXT     NOT NULL  DEFAULT 'sec_submissions_local'
   UNIQUE (entity_id, accession_number)
   ```

2. Add `models/sec_tickers.py`:

   ```
   id          INTEGER  PK autoincrement
   entity_id   INTEGER  FK entities.id  ON DELETE CASCADE
   ticker      TEXT     NOT NULL
   exchange    TEXT     NULLABLE
   is_active   INTEGER  DEFAULT 1
   UNIQUE (ticker, exchange)
   ```

3. Register in `models/__init__.py`.

4. Add migrations / schema creation steps consistent with `README.md` approach:
   - In this repo, new models typically require either a recreate step (`utils/recreate_sqlite_db.py`) or an idempotent alter/create migration helper. Prefer idempotent migrations.

**Exit criteria:**
- Tables exist; constraints are correct; tests validate basic insert/upsert.

**Handoff note:**
- Provide model/migration files changed and any new helper functions introduced.

---

## Session 6 — Priority 2B: Extend Submissions Parsing to Populate Filing + Ticker Tables (fresh session)

**Session Goal:** While walking `raw_data/submissions/*.json`, upsert `sec_filings` and `sec_tickers`.

**Read-First context pack:**
- `utils/populate_daily_values.py`
- `models/sec_filings.py`, `models/sec_tickers.py`
- `models/file_processing.py` (dedupe)

**Tasks:**

1. Add `_process_submission_filings(data, entity, session)` that reads `filings.recent` arrays:
   - `accessionNumber`, `form`, `filingDate`, `reportDate`, `primaryDocument`
   - Must upsert into `sec_filings` idempotently.

2. Add URL construction helper:

   ```python
   def _build_sec_filing_urls(cik_raw: str, accession_raw: str, primary_doc: str) -> dict:
       cik = str(int(cik_raw))
       acc_no_dashes = accession_raw.replace("-", "")
       base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_dashes}"
       return {
           "index_url":     f"{base}/{accession_raw}-index.htm",
           "document_url":  f"{base}/{primary_doc}",
           "full_text_url": f"{base}/{accession_raw}.txt",
       }
   ```

3. Populate `sec_tickers` where possible:
   - If filings data does not provide tickers directly, use what is available in submissions JSON (if present) and/or `entity_metadata` fields.
   - Always also create `entity_identifiers` with `scheme='ticker_exchange'` and normalized `value='{TICKER}:{EXCHANGE}'`.

4. Robust intermediate steps:
   - Add logging counts: number of filings inserted/updated per entity.
   - Ensure missing arrays or mismatched lengths are handled safely.

5. Tests using fixtures in `test_data/`:
   - Ensure at least one filing row is created from `submissions_sample.json`.
   - Ensure rerun is idempotent.

**Exit criteria:**
- Submissions ingestion populates structured filing rows.

**Handoff note:**
- Provide key assumptions about submissions JSON shape and any guards added.

---

## Session 7 — Priority 2C: Extend `FileProcessing` Tracking (fresh session)

**Session Goal:** Track ingestion source + inserted row counts for monitoring.

**Read-First context pack:**
- `README.md` ingestion flow and `file_processing` description
- `models/file_processing.py`
- `utils/migrate_sqlite_schema.py`

**Tasks:**
- Add columns to `file_processing`:
  - `source TEXT NOT NULL DEFAULT 'local'`
  - `record_count INTEGER NULLABLE`
- Update ingestion code to populate `source` and `record_count`.
- Tests: schema + at least one ingestion path sets `record_count`.

**Exit criteria:**
- Re-running ingestion does not duplicate and still records counts.

**Handoff note:**
- Provide which ingestion scopes set record_count (companyfacts, submissions, both).

---

## Session 8 — Priority 3A: Implement SEC HTTP Client Module (fresh session)

**Session Goal:** Add a reusable, rate-limited SEC API client.

**Read-First context pack:**
- `README.md` rate limit / user-agent constraints
- `settings.py` for user agent config
- existing network utilities (if any) under `utils/`

**Tasks:**
- Create `utils/sec_edgar_api.py`:
  - sliding-window rate limiter (max 9 req/s)
  - `User-Agent` injection
  - retry/backoff (3 attempts; respects `Retry-After`)
  - functions:
    - `fetch_filing_index(cik, accession_number) -> dict`
    - `fetch_filing_document(url) -> bytes`
    - `fetch_companyfacts(cik) -> dict`
    - `fetch_submissions(cik) -> dict`
    - `fetch_rss_feed(form_types: list[str]) -> list[dict]`
- Tests should mock HTTP.

**Exit criteria:**
- Client functions exist, are covered by tests, and enforce headers/rate limits.

**Handoff note:**
- Provide module public API and how to configure user agent through settings/env.

---

## Session 9 — Priority 3B: Create On-Demand SEC API Ingest Job (fresh session)

**Session Goal:** Download pending filings from `sec_filings` and store to disk + DB.

**Read-First context pack:**
- `README.md` jobs manager pattern (`api/jobs/manager.py`)
- `models/sec_filings.py`
- `utils/sec_edgar_api.py`

**Tasks:**
- Create `jobs/sec_api_ingest.py` (CLI runner):
  - selects `sec_filings` with `fetch_status in ('pending', NULL)`
  - downloads `document_url` (+ optional `full_text_url`)
  - saves to `raw_data/forms/{cik}/{accession_number}/`
  - updates `sec_filings.fetch_status`, `fetched_at`
  - supports `--form-types`, `--limit`, `--workers`
- Add job wrapper in `api/jobs/manager.py` following `PopulateDailyValuesJob` pattern.
- Tests: minimal integration test with mocked downloads.

**Exit criteria:**
- Job can be started/stopped; status is visible.

**Handoff note:**
- Provide CLI usage and what DB fields it touches.

---

## Session 10 — Priority 3C: Add `sec_filing_documents` + RSS Poller (fresh session)

**Session Goal:** Track per-document fetch status and enable near-real-time new filing detection.

**Read-First context pack:**
- `models/sec_filings.py`
- `README.md` constraints + identity rules (`entity_identifiers`)

**Tasks:**
- Add `models/sec_filing_documents.py`:

  ```
  id              INTEGER  PK autoincrement
  filing_id       INTEGER  FK sec_filings.id  ON DELETE CASCADE
  doc_type        TEXT     NOT NULL   -- 'primary', 'full_text', 'exhibit', 'index'
  filename        TEXT     NULLABLE
  local_path      TEXT     NULLABLE
  url             TEXT     NULLABLE
  size_bytes      INTEGER  NULLABLE
  fetched_at      DATETIME NULLABLE
  fetch_status    TEXT     DEFAULT 'pending'
  UNIQUE (filing_id, doc_type)
  ```

- Create `jobs/sec_rss_poller.py`:
  - polls EDGAR Atom feeds
  - extracts CIK
  - matches via `entity_identifiers (scheme='sec_cik')`
  - upserts `sec_filings` pending rows

**Exit criteria:**
- Poller can run without crashing and logs unknown CIKs.

**Handoff note:**
- Provide feed parsing assumptions and sample entries.

---

## Session 11 — Priority 4: Multi-Source Flexibility Schema Adjustments (fresh session)

**Session Goal:** Make fact + name tables traceable by source, period type, and accession.

**Read-First context pack:**
- `README.md` schema rules for facts and `value_names`
- `models/daily_values.py`, `models/value_names.py`, `models/entity_metadata.py`
- `utils/migrate_sqlite_schema.py`

**Tasks:**
- Add recommended columns using idempotent migrations:
  - `value_names.namespace TEXT NULLABLE`
  - `daily_values.source TEXT NULLABLE`
  - `daily_values.period_type TEXT NULLABLE` (`instant`/`duration`)
  - `daily_values.start_date_id INTEGER FK dates.id NULLABLE`
  - `daily_values.accession_number TEXT NULLABLE`
  - `entity_metadata.data_sources TEXT NULLABLE` (JSON array string)
  - `entity_metadata.last_sec_sync_at DATETIME NULLABLE`
- Add integration test running migrations against empty + seeded DB.

**Exit criteria:**
- Migrations are safe and schema remains consistent.

**Handoff note:**
- Provide migration function list and any backfill behavior.

---

## Session 12 — Priority 5: Data Sources Registry + GLEIF Ingestion Base Pattern (fresh session)

**Session Goal:** Add `data_sources` registry table and a reusable ingestion base class.

**Read-First context pack:**
- `README.md` multi-source philosophy
- `models/value_names.py` (source usage)

**Tasks:**
- Add `models/data_sources.py` and seed initial rows.
- Add `support/source_ingest_base.py` abstract base class.
- Implement `jobs/gleif_ingest.py` as first subclass.

**Exit criteria:**
- A second source can be added without schema rewrites.

**Handoff note:**
- Provide conventions for `source_name` and `FileProcessing.source` mapping.

---

## Session 13 — Priority 6: EFTS Search + API Endpoint + Admin UI (fresh session)

**Session Goal:** Enable keyword search for filings and expose it via the API and UI.

**Read-First context pack:**
- `README.md` Flask blueprint layout
- `api/api_v1/blueprint.py` and existing `api/pages/*`
- `templates/pages/`

**Tasks:**
- Create `utils/sec_efts_client.py`.
- Add `/api/v1/filings/search` endpoint.
- Extend admin UI with a minimal search form.

**Exit criteria:**
- Endpoint returns results; UI renders; tests cover endpoint.

---

## Implementation Order Summary

This is unchanged in spirit, but now mapped to fresh sessions:

```
Session 0  →  baseline orientation + invariants
Session 1  →  entity_relationships model + UUID derivation helper
Session 2  →  entity_identifiers confidence/timestamps
Session 3  →  scheme normalization extensions
Session 4  →  conflicting identifier integrity behavior
Session 5  →  sec_filings + sec_tickers models
Session 6  →  populate_daily_values submissions → filings/tickers ingestion
Session 7  →  file_processing source + record_count
Session 8  →  utils/sec_edgar_api.py client
Session 9  →  jobs/sec_api_ingest.py + job manager wiring
Session 10 →  sec_filing_documents + RSS poller
Session 11 →  multi-source DB adjustments
Session 12 →  data_sources registry + GLEIF job + ingest base class
Session 13 →  EFTS search + API endpoint + UI
```

Each session is independently deployable and should end with a passing pytest run and a clear handoff note for the next fresh session.
