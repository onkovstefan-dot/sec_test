# sec_api_ingest: no pending filings selected — investigation checklist

## What happened
If `jobs/sec_api_ingest.py` starts but logs/prints **"No pending filings selected"**, it means the query returned **zero** rows:

- `sec_filings.fetch_status IS NULL` **or** `sec_filings.fetch_status = 'pending'`
- optionally filtered by `--form-types` (interactive selection can also filter)

So the job didn’t crash; it simply had nothing to ingest.

## Quick checks (DB)
1. **Confirm the DB you think you’re using**
   - Check startup diagnostics in logs for `engine.url` / `DATABASE_URL`.
   - Make sure you aren’t pointing at an empty test DB.

2. **Check whether any filings exist at all**
   - Count rows in `sec_filings`.

3. **Check for pending rows**
   - Count rows where `fetch_status IS NULL OR fetch_status='pending'`.

4. **Check if your filter excludes everything**
   - Group pending filings by `form_type` to see what’s actually available.
   - If you only have e.g. `8-K` pending but you selected `10-K`, selection will be empty.

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

## How to reproduce with maximum signal
- Run with `--log-level DEBUG`.
- Run without `--form-types` to avoid filtering (or choose “All available pending form types” in the interactive menu).

## Notes
The interactive menu in `sec_api_ingest.py` was updated to only show form types that currently have **pending** rows in the DB, so selecting an unavailable form type should be harder now.
