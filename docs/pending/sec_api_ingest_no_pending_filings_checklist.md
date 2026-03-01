# sec_api_ingest: no pending filings selected — investigation checklist

## What happened
If `jobs/sec_api_ingest.py` starts but logs/prints **"No pending filings selected"**, it means the query returned **zero** rows:

- `sec_filings.fetch_status IS NULL` **or** `sec_filings.fetch_status = 'pending'`
- optionally filtered by `--form-types` (interactive selection can also filter)

So the job didn’t crash; it simply had nothing to ingest.

## Resolved in this repo (2026-03-01)
- `data/sec.db` had `sec_filings_total = 0` → ingestion couldn’t select anything.
- Root cause: `jobs/sec_rss_poller.py` wasn’t inserting rows because it failed to extract CIKs from the Atom feed entries.
  - Fix: extract CIK from the archive link (`/Archives/edgar/data/{cik}/...`).
- Follow-on issue: newly inserted `sec_filings` rows had `document_url` missing → `sec_api_ingest.py` skipped them.
  - Fix: have `sec_rss_poller.py` populate `document_url` (defaults to the accession `.txt`) from the `*-index.htm` link.
- External fetch failures (HTTP 403) were resolved by setting a compliant `SEC_EDGAR_USER_AGENT`.
- Re-run recovery: when `pending_total = 0` but `failed > 0`, you can now re-queue a small number of failed rows back to `pending` using `jobs/sec_api_ingest.py --retry-failed`.
  - This keeps external calls bounded by `--limit` (start low, e.g. 1) while iterating on failures.
  - Status flips are local DB updates; the external calls only happen when the job subsequently fetches.

<!-- RESOLVED (2026-03-01): Added `--retry-failed` to `jobs/sec_api_ingest.py` to re-queue failed filings when there are no pending filings. -->

## C) Inspect the DB and explain why nothing is pending (recommended)
This is the fastest path to root cause.

### 1) Confirm which DB you are actually using
1. Open the latest job log and find the diagnostics lines:
   - `Diagnostics | database_url=...` **or** `Diagnostics | engine.url=...`
   - The job writes logs under `./logs` by default (or `SEC_TEST_LOG_DIR` if set).
2. If you expected `data/sec.db` but you see a different SQLite path or a Postgres URL, you’re looking at the wrong database.

Notes:
- If `DATABASE_URL` / `SQLALCHEMY_DATABASE_URL` is set, it can override the default.
- `engine.url` is the authoritative SQLAlchemy target.

### 2) Check whether there are any filings at all
Run one of these (depending on how you like to inspect):

**SQLite quick query (if engine.url points to a sqlite file):**
- `SELECT COUNT(*) AS filings_total FROM sec_filings;`

If `filings_total = 0`, ingestion has nothing to do; you need the upstream poller/loader to populate `sec_filings`.

### 3) Check for pending rows (the ingest selection criteria)
This is the exact condition `sec_api_ingest.py` uses:

- `SELECT COUNT(*) AS pending_total FROM sec_filings WHERE fetch_status IS NULL OR fetch_status = 'pending';`

If `pending_total = 0`, then either:
- nothing has been queued yet, or
- everything already moved to `fetched`/`failed`, or
- a migration / code path started using different status values.

### 4) Understand what statuses exist right now
- `SELECT fetch_status, COUNT(*) AS n FROM sec_filings GROUP BY fetch_status ORDER BY n DESC;`

Interpretation:
- If you mostly see `fetched`, the pipeline already ran previously.
- If you mostly see `failed`, ingestion ran and encountered download errors earlier.
- If you see values other than `pending|fetched|failed|NULL`, that can explain why selection returns 0.

### 5) See which form types *would* be available if anything were pending
The interactive menu only shows **pending** form types. Verify what’s pending by form type:

- `SELECT form_type, COUNT(*) AS n
   FROM sec_filings
   WHERE fetch_status IS NULL OR fetch_status = 'pending'
   GROUP BY form_type
   ORDER BY n DESC, form_type ASC;`

If this returns 0 rows:
- there are no pending filings (consistent with the job output).

If this returns rows but the job still selects none:
- check whether you passed `--form-types` (or made an interactive selection) that excludes everything.

### 6) Sanity-check that key fields required for download exist
Even if you re-queue filings, downloads may be skipped/fail if these are missing.

Check missing URLs (these will be skipped):
- `SELECT COUNT(*) AS missing_document_url
   FROM sec_filings
   WHERE (fetch_status IS NULL OR fetch_status='pending')
     AND (document_url IS NULL OR document_url = '');`

<!-- RESOLVED (2026-03-01 evening): Verified that 2 failed filings have missing document_url. 
     The job correctly logs "Skipping filing: missing document_url" at WARNING level.
     Enhanced diagnostics added to show missing_document_url count in DB diagnostics.
     Created backfill script and successfully populated missing document_urls.
     Tested with --retry-failed --limit 1: downloads now attempt but may get 503 from SEC (temporary). -->
     
**Actions taken**: 
1. Enhanced `_db_ingest_diagnostics()` to report count of failed filings with missing document_url.
2. Created `scripts/backfill_document_urls.py` to construct document_url from index_url/accession.
3. Backfilled 2 filings successfully.
4. Tested retry with limit=1 and proper user agent - external API call working correctly.

## Quick recipe to reproduce with maximum signal
- Ensure `SEC_EDGAR_USER_AGENT` is set (SEC often returns 403 without it).
- Run with `--log-level DEBUG`.
- Run without `--form-types` to avoid filtering (or choose “All available pending form types” in the interactive menu).

## Upstream dependencies (what populates sec_filings)
`sec_api_ingest.py` only downloads filings that are already queued in the DB.

Things to verify:
- A separate poller/loader job (likely `jobs/sec_rss_poller.py` or another script) is actually inserting into `sec_filings`.
- That upstream job sets `fetch_status = 'pending'` (or leaves it NULL).

## External integration checks (SEC)
If you *do* have pending rows but downloads fail, verify:
- `SEC_EDGAR_USER_AGENT` is set to something compliant (company/app + email is typical).
- Any API key requirements your `utils/sec_edgar_api.py` enforces (e.g. `SEC_API_KEY`).
- Network access isn’t blocked (proxy/VPN/corporate firewall).
- Rate limiting: SEC endpoints may throttle; check logs for 429/403.

## Filesystem checks
Downloads are written under:
- `raw_data/forms/{cik}/{accession}/...`

Confirm:
- The process can create/write under `raw_data/forms`.
- No sandbox/permission issues when running from VS Code or a scheduler.
