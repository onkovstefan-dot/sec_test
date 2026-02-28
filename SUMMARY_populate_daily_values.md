# Summary: `utils/populate_daily_values.py` run + `populate_daily_values.log`

## Executive summary
The current `populate_daily_values.log` shows **one dominant repetitive issue**:

- Some files in `raw_data/submissions/` are **not full SEC “submissions” JSONs** (`{"cik": ..., "filings": {"recent": ...}}`).
- Instead, they are **flattened “recent filings” payloads** (top-level arrays like `accessionNumber`, `filingDate`, `reportDate`, etc.) with **no `cik`** and **no `filings.recent`**.

Because `utils/populate_daily_values.py` expects `data["filings"]["recent"]`, these files cannot be processed by the current pipeline and are currently being **skipped with a warning**.

## What the log says (patterns, not per-file)
In the current log snapshot:

- `INFO`: many entries (normal processing)
- `WARNING`: a few entries
- `ERROR`: none in the current run

All warnings follow the same pattern:

- `Skipping file <name>: appears to be flattened submissions payload (no top-level 'cik'/'filings')`

### Example “problem files”
Examples from the log:
- `CIK0000750556-submissions-002.json`
- `CIK0000097216-submissions-003.json`
- `CIK0000821002-submissions-001.json`

## Do all files have the same structure?
No.

There are (at least) **two structures** present in `raw_data/submissions/`:

1) **Full submissions schema** (expected by current code)
   - Has top-level `cik`
   - Has `filings.recent` dict of arrays
   - Example (from sampled files): `CIK0001134582.json`

2) **Flattened recent-filings schema** (currently skipped)
   - No top-level `cik`
   - No `filings`
   - Has top-level arrays: `accessionNumber`, `filingDate`, `reportDate`, `form`, ...
   - These appear to be equivalent to what would normally live at `filings.recent`

## Why these files exist (likely cause)
Your workspace already contains a model named `models/submissions_flat.py`, which strongly suggests you intentionally (or via a different pipeline) produced a flattened version of the SEC submissions data.

So the `raw_data/submissions/` directory likely contains a mix of:
- raw SEC submissions JSONs
- flattened “recent” payloads

This is a *data ingestion/pipeline consistency* issue more than a DB issue.

## Do we need another DB table (not only `DailyValue`)?
Probably yes, depending on the goal.

### If your goal is “store any numeric value keyed by entity/date/value_name”
Then `DailyValue` is fine for values that are numeric (or coercible). But many `filings.recent` fields are:
- strings (`form`, `primaryDocument`, etc.)
- booleans (`isXBRL`)
- identifiers (`accessionNumber`)

Today the script tries `float(val)` and stores `None` on failure. That loses information for non-numeric fields.

**Recommendation**:
- Keep `DailyValue` for numeric measures.
- Add a second table for non-numeric values, e.g. `DailyValueText` (or a generic `DailyValueRaw` with JSON/text columns).

### If your goal is “store SEC submissions/filings as filings” (more relational)
Then a more appropriate schema is to store each filing as a row:
- entity_id
- accession_number
- filing_date
- report_date
- form
- etc.

That would be a separate `Filing` table (or similar). `DailyValue` isn’t a natural fit for this.

## How to proceed (recommended plan)

### Step 1 — Decide what `raw_data/submissions/` is supposed to contain
Pick one:

**Option A (preferred for simplicity):**
- `raw_data/submissions/` contains *only full raw submissions JSON*.
- flattened payloads go to another folder, e.g. `raw_data/submissions_flat/`.

**Option B:**
- Keep the mix, but teach the loader to recognize and handle both schemas.

### Step 2 — Enhance runtime handling in `utils/populate_daily_values.py`
Suggested improvements:

1) **Schema routing**
   - If full schema: `recent = data['filings']['recent']`
   - If flattened schema: treat `recent = data` and infer `cik` from filename
   - If neither: log `unknown_schema` and skip

2) **Avoid per-row commits (major performance)**
   - Current code commits in the inner loop.
   - Switch to batching (e.g., collect rows, `session.add_all`, commit per file or per N rows).

3) **Reduce DB queries for duplicates**
   - Current code does a query per value to check duplicates.
   - Prefer a DB-level unique constraint on (`entity_id`, `value_name_id`, `date_id`) and catch `IntegrityError`.

4) **Value typing**
   - Only store numeric fields in `DailyValue`.
   - For non-numeric values, either:
     - store in `DailyValueText`, or
     - skip and log (but then you knowingly lose those fields).

### Step 3 — Enhance logging for investigation
Recommended logging additions:

1) **Per-file summary logs** (INFO)
   - schema detected (full/flattened/unknown)
   - counts: inserted, duplicates skipped, missing dates skipped, invalid dates, non-numeric, etc.

2) **Aggregate totals at end** (INFO)
   - skip reason counts
   - exception type counts

3) **Sampled file list per skip reason** (INFO)
   - For each skip reason, store up to N filenames (e.g., 10) in the log for quick follow-up.

4) **Separate logs (optional)**
   - `populate_daily_values.info.log` (INFO)
   - `populate_daily_values.errors.log` (ERROR only)

## Quick actionable next steps
1) Confirm whether `raw_data/submissions` is expected to include flattened payloads.
2) If yes: update loader to process flattened schema as `recent` + infer `cik`.
3) Decide whether to create a `Filing` table and/or a `DailyValueText` table.
4) Implement batching + unique constraint to improve runtime drastically.
