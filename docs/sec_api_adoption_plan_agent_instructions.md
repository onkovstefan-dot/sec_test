# SEC API Adoption Plan — Agent Instructions (Copy/Paste Sessions)

This file is a **copy/paste playbook** for running `docs/sec_api_adoption_plan.md` as **separate, consecutive, fresh AI-agent sessions**.

- **You must start a new chat/session for each session below.**
- In each new session, paste **exactly one** prompt block from this file.
- Each block includes what the agent must read, what to implement, and what to hand back.

Project source-of-truth: `README.md` (repo layout, schema invariants, ingestion flow, testing).

---

## Global output rule (applies to every session)

At the **very bottom of your final response** in each session, include a short summary section with this exact heading:

**Session Summary (for handoff)**

Keep it brief (3-8 bullets) and include:
- what changed (or "no code changes")
- files touched/inspected
- migrations/helpers added (names)
- tests added/updated (names) and whether they pass
- any pitfalls/assumptions

---

## Session 0 — Baseline Orientation & Inventory (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 0 of the SEC roadmap.

Goal: Baseline orientation. Understand the repo and document invariants so later sessions can operate safely.

Read FIRST (mandatory):
- README.md (project goal, repo layout, DB schema rules, ingestion flow, testing approach)
- docs/sec_api_adoption_plan.md (the roadmap)
- db.py, settings.py
- models/__init__.py, models/entities.py, models/entity_identifiers.py, models/file_processing.py
- utils/migrate_sqlite_schema.py, utils/populate_daily_values.py
- api/jobs/manager.py
- pytests/conftest.py, pyproject.toml (pytest config)

Tasks:
1) Identify the exact model-registration pattern (how Base is imported, how models are registered in models/__init__.py).
2) Identify how schema creation/migration works today:
   - how new tables are created
   - how ALTER TABLE migrations are performed (idempotent helpers in utils/migrate_sqlite_schema.py)
3) Identify ingestion idempotence mechanism:
   - how FileProcessing prevents duplicate processing
   - how populate_daily_values.py uses it
4) Identify the test entry points and conventions:
   - pytest invocation
   - how temp DB fixtures are created

Output requirements:
- Produce a short “Session 0 inventory note” with bullet points for (1)-(4) plus any pitfalls.
- Do NOT change code in Session 0.

Exit criteria:
- Inventory note is complete enough that a new agent can implement migrations/models/tests without guessing.

Handoff:
- Return the inventory note and list of files inspected.

---

## Session 1 — Priority 1A: Add Entity Relationships Model (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 1 of the SEC roadmap.

Goal: Add entity-to-entity relationship edges and a deterministic canonical UUID derivation helper.

Read FIRST (mandatory):
- README.md (DB schema rules; model registration; testing expectations)
- docs/sec_api_adoption_plan.md (Session 1 section)
- models/entities.py, models/entity_identifiers.py
- utils/migrate_sqlite_schema.py, utils/recreate_sqlite_db.py
- pytests/ (scan existing patterns)

Tasks:
1) Add new model file models/entity_relationships.py with schema:
   - id INTEGER PK autoincrement
   - parent_entity_id INTEGER FK entities.id ON DELETE CASCADE
   - child_entity_id INTEGER FK entities.id ON DELETE CASCADE
   - relationship_type TEXT NOT NULL
   - ownership_pct REAL NULL
   - effective_from DATE NULL
   - effective_to DATE NULL
   - source TEXT NULL
   - UNIQUE(parent_entity_id, child_entity_id, relationship_type)
2) Register the model in models/__init__.py (required).
3) Implement deterministic UUID derivation helper (do NOT change global entity canonical_uuid generation):
   uuid5(NAMESPACE_URL, f"{parent_canonical_uuid}:{relationship_type}:{child_scheme}:{child_value}")
   - Put helper in a small utility module (e.g., utils/entity_identity.py).
4) Ensure DB schema creation/migration path includes the new table:
   - Prefer an idempotent create-table migration helper in utils/migrate_sqlite_schema.py.
5) Add pytest unit tests:
   - determinism (same inputs => same UUID)
   - difference (change relationship_type or child identifier => different UUID)

Execution requirements:
- Follow the repo’s existing patterns from README.md.
- Keep migrations idempotent.
- Ensure pytest passes.

Exit criteria:
- New model exists and is registered.
- DB migration path creates the table.
- Tests pass.

Handoff:
- Summarize file changes, migration function names, and helper function signature.

---

## Session 2 — Priority 1B: Harden entity_identifiers columns (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 2 of the SEC roadmap.

Goal: Add confidence and timestamps to entity_identifiers for auditability.

Read FIRST (mandatory):
- README.md (entity_identifiers schema + rules)
- docs/sec_api_adoption_plan.md (Session 2 section)
- models/entity_identifiers.py
- utils/migrate_sqlite_schema.py
- utils/time_utils.py (utcnow)
- utils/populate_daily_values.py (get_or_create_entity_by_identifier)

Tasks:
1) Add 3 columns to entity_identifiers via idempotent migrations:
   - confidence TEXT NOT NULL DEFAULT 'authoritative'
   - added_at DATETIME NOT NULL DEFAULT utcnow
   - last_seen_at DATETIME NULL
2) Update models/entity_identifiers.py accordingly.
3) Update get_or_create_entity_by_identifier so new rows set added_at and (if appropriate) last_seen_at.
4) Add tests:
   - migration adds the columns
   - inserting a new identifier sets defaults

Exit criteria:
- Migration idempotent.
- Tests pass.

Handoff:
- Provide migration helper names + any call-site updates.

---

## Session 3 — Priority 1C: Extend identifier normalization schemes (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 3 of the SEC roadmap.

Goal: Extend _scheme_alias/_normalize_identifier_value to cover planned schemes, with tests.

Read FIRST (mandatory):
- README.md (identity resolution rules)
- docs/sec_api_adoption_plan.md (Session 3 section)
- utils/populate_daily_values.py
- pytests patterns for table-driven tests

Tasks:
1) Extend scheme aliasing + normalization in utils/populate_daily_values.py for:
   - gleif_lei: uppercase; exactly 20 alnum chars
   - isin: uppercase; exactly 12 chars
   - gb_companies_house: zero-pad to 8 digits
   - fr_siren: digits only; exactly 9 digits
   - eu_vat: strip spaces; uppercase
   - ticker_exchange: format '{TICKER}:{MIC}' uppercase
2) Decide and document consistent error behavior for invalid formats (raise vs return None) and test it.
3) Add table-driven pytests for:
   - valid normalization cases
   - invalid cases

Exit criteria:
- Normalization deterministic.
- Tests pass.

Handoff:
- Provide normalization table (inputs/expected outputs) and invalid-case behavior.

---

## Session 4 — Priority 1D: Conflicting identifier integrity behavior (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 4 of the SEC roadmap.

Goal: Ensure get_or_create_entity_by_identifier fails safely when (scheme,value) is claimed by a different entity.

Read FIRST (mandatory):
- README.md (identity rules)
- docs/sec_api_adoption_plan.md (Session 4 section)
- utils/populate_daily_values.py (get_or_create_entity_by_identifier)
- models/entity_identifiers.py (constraints)

Tasks:
1) Implement/adjust logic so that if (scheme,value) exists for a different entity_id, raise IntegrityError (or a consistent explicit exception).
2) Add tests that simulate two entities attempting to claim the same identifier.

Exit criteria:
- Conflicts are detected and tested.

Handoff:
- Document exception type/message and exactly where raised.

---

## Session 5 — Priority 2A: Add sec_filings + sec_tickers models (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 5 of the SEC roadmap.

Goal: Add structured tables for submissions-derived filings and tickers.

Read FIRST (mandatory):
- README.md (model registration, schema invariants)
- docs/sec_api_adoption_plan.md (Session 5 section)
- utils/migrate_sqlite_schema.py and any existing create-table helpers
- utils/populate_daily_values.py (submissions parsing)

Tasks:
1) Add models/sec_filings.py with columns and constraints from the plan.
2) Add models/sec_tickers.py with columns and constraints from the plan.
3) Register both in models/__init__.py.
4) Add idempotent migrations/create-table helpers for both tables in utils/migrate_sqlite_schema.py.
5) Add basic tests that tables exist and can insert a row.

Exit criteria:
- Tables exist with correct uniqueness constraints.
- Tests pass.

Handoff:
- List new migration functions and any helper utilities added.

---

## Session 6 — Priority 2B: Populate sec_filings + sec_tickers from submissions parsing (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 6 of the SEC roadmap.

Goal: Extend utils/populate_daily_values.py submissions pass to upsert sec_filings and sec_tickers idempotently.

Read FIRST (mandatory):
- README.md (ingestion flow; FileProcessing dedupe)
- docs/sec_api_adoption_plan.md (Session 6 section)
- utils/populate_daily_values.py
- models/sec_filings.py, models/sec_tickers.py
- test_data/submissions_sample.json and existing tests that reference submissions

Tasks:
1) Implement _process_submission_filings(data, entity, session) to read filings.recent arrays:
   - accessionNumber, form, filingDate, reportDate, primaryDocument
   - upsert into sec_filings with UNIQUE(entity_id, accession_number)
2) Implement _build_sec_filing_urls(cik_raw, accession_raw, primary_doc) helper as per plan.
3) Populate sec_tickers where possible; always also create entity_identifiers with scheme='ticker_exchange'.
4) Add safe guards for missing fields/mismatched lengths; add logging of inserted/updated counts.
5) Update/add tests using test_data/submissions_sample.json:
   - creates at least one sec_filings row
   - rerun is idempotent

Exit criteria:
- Submissions ingestion populates structured tables.
- Tests pass.

Handoff:
- Document any assumptions about submissions JSON shape and any guard logic.

---

## Session 7 — Priority 2C: Extend FileProcessing tracking (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 7 of the SEC roadmap.

Goal: Add FileProcessing.source and FileProcessing.record_count and populate them.

Read FIRST (mandatory):
- README.md (file_processing role)
- docs/sec_api_adoption_plan.md (Session 7 section)
- models/file_processing.py
- utils/migrate_sqlite_schema.py
- utils/populate_daily_values.py

Tasks:
1) Add columns via idempotent migrations:
   - source TEXT NOT NULL DEFAULT 'local'
   - record_count INTEGER NULL
2) Update SQLAlchemy model models/file_processing.py.
3) Update ingestion to record source and record_count (companyfacts/submissions as appropriate).
4) Add tests for migration + at least one ingestion path sets record_count.

Exit criteria:
- Idempotent, tests pass.

Handoff:
- Explain exactly where record_count is computed and stored.

---

## Session 8 — Priority 3A: Implement SEC HTTP client (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 8 of the SEC roadmap.

Goal: Add rate-limited, user-agent enforced SEC HTTP client module.

Read FIRST (mandatory):
- README.md (SEC constraints: rate limit + User-Agent)
- docs/sec_api_adoption_plan.md (Session 8 section)
- settings.py (User-Agent configuration)

Tasks:
1) Create utils/sec_edgar_api.py implementing:
   - sliding-window rate limiter (max 9 req/s)
   - automatic User-Agent
   - retry/backoff (3 attempts; respects Retry-After)
   - functions: fetch_filing_index, fetch_filing_document, fetch_companyfacts, fetch_submissions, fetch_rss_feed
2) Add tests with mocked HTTP ensuring:
   - User-Agent always present
   - rate limiter invoked
   - retry behavior triggers on 429/5xx

Exit criteria:
- Tests pass.

Handoff:
- Provide module API and configuration instructions.

---

## Session 9 — Priority 3B: Create SEC API ingest job + job-manager wiring (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 9 of the SEC roadmap.

Goal: Add on-demand job to fetch pending filings and store to raw_data/forms/... and update DB status.

Read FIRST (mandatory):
- README.md (jobs manager pattern)
- docs/sec_api_adoption_plan.md (Session 9 section)
- api/jobs/manager.py
- models/sec_filings.py
- utils/sec_edgar_api.py

Tasks:
1) Create jobs/sec_api_ingest.py CLI runner with --form-types/--limit/--workers.
2) Implement file saving to raw_data/forms/{cik}/{accession_number}/.
3) Update sec_filings.fetch_status + fetched_at.
4) Add job wrapper class in api/jobs/manager.py (similar to PopulateDailyValuesJob).
5) Add tests (mock network) verifying status update + file write call.

Exit criteria:
- Job starts/stops, status visible, tests pass.

Handoff:
- Provide CLI usage and list of DB fields updated.

---

## Session 10 — Priority 3C: sec_filing_documents + RSS poller (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 10 of the SEC roadmap.

Goal: Track per-document fetch and poll RSS/Atom for new filings.

Read FIRST (mandatory):
- README.md (identity rules)
- docs/sec_api_adoption_plan.md (Session 10 section)
- models/sec_filings.py

Tasks:
1) Add models/sec_filing_documents.py per plan with UNIQUE(filing_id, doc_type).
2) Add idempotent migration/create-table helper.
3) Create jobs/sec_rss_poller.py:
   - polls EDGAR Atom
   - extracts CIK
   - matches entity_identifiers(scheme='sec_cik')
   - upserts sec_filings pending rows
4) Add tests with mocked feed response.

Exit criteria:
- Poller runs without crashing; unknown CIKs logged; tests pass.

Handoff:
- Provide feed parsing assumptions + sample parsing function signature.

---

## Session 11 — Priority 4: Multi-source schema adjustments (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 11 of the SEC roadmap.

Goal: Add schema columns enabling multi-source + period typing + accession traceability.

Read FIRST (mandatory):
- README.md (schema invariants)
- docs/sec_api_adoption_plan.md (Session 11 section)
- utils/migrate_sqlite_schema.py
- models/daily_values.py, models/value_names.py, models/entity_metadata.py

Tasks:
1) Add idempotent migrations for:
   - value_names.namespace TEXT NULL
   - daily_values.source TEXT NULL
   - daily_values.period_type TEXT NULL
   - daily_values.start_date_id INTEGER FK dates.id NULL
   - daily_values.accession_number TEXT NULL
   - entity_metadata.data_sources TEXT NULL
   - entity_metadata.last_sec_sync_at DATETIME NULL
2) Update the SQLAlchemy models accordingly.
3) Add integration test: apply migrations to empty DB and seeded DB; assert schema integrity.

Exit criteria:
- Migrations safe and idempotent; tests pass.

Handoff:
- Provide list of migration helper names and any backfill performed.

---

## Session 12 — Priority 5: data_sources registry + GLEIF ingest base pattern (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 12 of the SEC roadmap.

Goal: Add data_sources lookup table + reusable ingestion base class + initial GLEIF job.

Read FIRST (mandatory):
- README.md (multi-source philosophy)
- docs/sec_api_adoption_plan.md (Session 12 section)
- models/value_names.py

Tasks:
1) Add models/data_sources.py + migration + seed initial sources.
2) Add support/source_ingest_base.py base class.
3) Implement jobs/gleif_ingest.py as first subclass.
4) Add tests for data_sources presence and seed rows.

Exit criteria:
- Adding a second source is straightforward; tests pass.

Handoff:
- Provide conventions for source naming and how it maps to FileProcessing.source.

---

## Session 13 — Priority 6: EFTS search + /api/v1/filings/search + UI (paste into a fresh session)

Paste:

You are an AI coding agent. This is Session 13 of the SEC roadmap.

Goal: Implement filing keyword search via SEC EFTS as fallback and expose it via API + minimal UI.

Read FIRST (mandatory):
- README.md (Flask blueprint layout)
- docs/sec_api_adoption_plan.md (Session 13 section)
- api/api_v1/blueprint.py and existing api/pages/* patterns
- templates/pages/*

Tasks:
1) Create utils/sec_efts_client.py (HTTP wrapper + parsing).
2) Add /api/v1/filings/search endpoint:
   - params: q, form_type, cik, date_from, date_to, limit
   - prefer local sec_filings first; fallback to EFTS
3) Add minimal admin UI search form under templates/pages/.
4) Add tests for endpoint behavior with mocked EFTS.

Exit criteria:
- Endpoint works and tests pass.

Handoff:
- Provide example requests and response shape.
