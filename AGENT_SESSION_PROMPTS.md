# AI Agent Session Prompts (for `SUMMARY_enhancements_v3.md`)

Use **one session block per fresh chat**. Copy/paste the block for the milestone you want to execute.

## Optional session header (prepend to every session prompt)

- Preserve all URLs and behavior. No redesigns.
- Keep changes small and finishable in one session.
- After changes: run `pytest pytests/` and run the smoke checklist.
- If anything breaks: stop, fix, re-test, then report.

---

## Session 0 — Milestone 0 (from `SUMMARY_enhancements_v3.md`): Baseline documentation (NO code changes)

**Before you start (check prior work):**
- If `docs/SMOKE_TEST.md` and/or `docs/CURRENT_ROUTES.md` already exist, verify they match Milestone 0 requirements and **do not overwrite** unless they’re incomplete/incorrect.
- If `pytest pytests/` was already run for this baseline, re-run only if you changed anything (Milestone 0: you should not).

**Instructions to agent:**
1. Read `SUMMARY_enhancements_v3.md` fully and determine Milestone 0 is the target.
2. Read `api/routes.py` completely and extract **all** routes (`@...route(...)`) including path, methods, and function name.
3. Create `docs/SMOKE_TEST.md` containing the smoke test checklist from the plan.
4. Create `docs/CURRENT_ROUTES.md` listing every route found (one per line, include methods + path + handler).
5. Run the existing test suite (`pytest pytests/`) and fix nothing unless tests are already failing (if failing, report failures and stop).
6. Manually validate 2–3 critical routes from the smoke list (home, check-cik POST redirect, admin page load).
7. Report: files created, tests status, any issues discovered. **Stop after Milestone 0.**

**Acceptance criteria to report:**
- `docs/SMOKE_TEST.md` exists
- `docs/CURRENT_ROUTES.md` exists
- `pytest pytests/` passes (or failures documented)
- No source code modified

---

## Session 1 — Milestone 1 (from `SUMMARY_enhancements_v3.md`): Templates + static scaffolding (file creation only)

**Before you start (check prior work):**
- Confirm Milestone 0 deliverables exist (`docs/SMOKE_TEST.md`, `docs/CURRENT_ROUTES.md`). If missing, stop and do Milestone 0 first.
- If `templates/` or `static/` already exist, compare against the planned structure and **only add what’s missing** (avoid overwriting files unless explicitly required).

**Instructions to agent:**
1. Confirm Milestone 0 deliverables exist; if missing, stop and do Milestone 0 first.
2. Create directories exactly as planned:
   - `templates/pages`, `templates/components`, `templates/errors`
   - `static/css`, `static/js`
   - `docs` (if not existing)
3. Create `templates/base.html` with `{% block title %}`, `{% block head %}`, `{% block content %}`, `{% block scripts %}` and CSS link via `url_for('static', filename='css/app.css')`. Include navbar include.
4. Create:
   - `templates/components/navbar.html`
   - `templates/components/flash.html`
5. Create CSS:
   - `static/css/app.css` (global styles per plan; ok to be minimal but valid)
   - `static/css/components.css` (component styles per plan)
6. Create placeholder page templates that extend `base.html`:
   - `templates/pages/home.html`
   - `templates/pages/check_cik.html`
   - `templates/pages/daily_values.html`
   - `templates/pages/admin.html`
   - `templates/pages/db_check.html`
7. Create JS placeholders:
   - `static/js/admin.js`
   - `static/js/daily_values.js`
8. Validation:
   - Start app and verify static files load in browser:
     - `/static/css/app.css`
     - `/static/js/admin.js`
   - Run smoke tests (no routes changed, so everything should still work).
9. Report: files/dirs created + validation results. **Stop after Milestone 1.**

**Constraints:**
- Do NOT change route behavior in this milestone.

---

## Session 2 — Milestone 2 (from `SUMMARY_enhancements_v3.md`): Migrate `/admin` to templates/static

**Before you start (check prior work):**
- Confirm Milestone 1 scaffolding exists (`templates/base.html`, component templates, `static/css/app.css`). If missing, stop and complete Milestone 1 first.
- If `templates/pages/admin.html` and/or `static/js/admin.js` already exist, update them in-place and preserve current behavior/variables.

**Instructions to agent:**
1. Read current `/admin` implementation in `api/routes.py` (GET + any related admin endpoints).
2. Move the inline `/admin` HTML into `templates/pages/admin.html` using Jinja variables that match what the route currently provides.
3. Ensure `templates/pages/admin.html` loads `static/js/admin.js` via `{% block scripts %}`.
4. Move any inline admin CSS into `static/css/app.css` or create `static/css/admin.css` (only if needed). Avoid inline `<style>` in the template.
5. Move any inline admin JS into `static/js/admin.js`. Avoid inline `<script>` in the template.
6. Update the `/admin` route to use `render_template('pages/admin.html', ...)` with the same variables/behavior as before.
7. Validation:
   - Full smoke test list (especially all admin actions, confirmation tokens).
   - Check browser console for JS errors.
8. Report: what changed + what was validated. **Stop after Milestone 2.**

**Constraints:**
- Preserve URLs and behavior.
- Keep confirmation tokens identical in meaning/flow.

---

## Session 3 — Milestone 3 (from `SUMMARY_enhancements_v3.md`): Extract background job logic to `api/jobs/manager.py`

**Before you start (check prior work):**
- If `api/jobs/manager.py` already exists, inspect it and extend/refactor it instead of recreating it.
- Confirm Milestone 2 `/admin` template migration is done (or note any drift) before changing admin job plumbing.

**Instructions to agent:**
1. Identify all background-job state, locks, helpers (e.g., “last log line”) currently inside `api/routes.py`.
2. Create:
   - `api/jobs/__init__.py`
   - `api/jobs/manager.py`
3. Implement job managers (populate + recreate) that encapsulate:
   - start helpers
   - cooperative stop flag for populate
   - last-log-line helper (tail best-effort)
   - “ensure schema exists” helper before populate
4. Update admin routes to use the managers instead of globals in `api/routes.py`.
5. Remove/retire the old global dicts/locks/helpers from `api/routes.py`.
6. Validation:
   - Start/stop populate job works
   - Recreate DB job works
   - `/admin` status still shows correctly
   - Smoke tests pass
7. Report: new module API + what you removed from routes.py. **Stop after Milestone 3.**

**Constraints:**
- Thread safety must be preserved (locks).
- Keep behavior stable.

---

## Session 4 — Milestone 4a (from `SUMMARY_enhancements_v3.md`): Split routes — Home + Check CIK into `api/pages/*`

**Before you start (check prior work):**
- Confirm Milestone 3 job manager exists if later milestones depend on it; if not present yet, that’s OK for 4a but note it.
- If `api/blueprint.py` or any `api/pages/*.py` already exists, modify/register incrementally—do not duplicate blueprints or register the same route twice.

**Instructions to agent:**
1. Create `api/pages/__init__.py`.
2. Create `api/pages/home.py` and `api/pages/check_cik.py` and **copy** the existing handlers from `api/routes.py`.
   - Keep `render_template_string` for these pages for now (templates migrated later in M9).
3. Create `api/blueprint.py` with a `create_api_blueprint()` that registers these page blueprints.
4. Update `app.py` to register the new blueprint instead of depending on monolithic routes module.
5. In `api/routes.py`, comment out or remove only the migrated routes (keep file for reference for now).
6. Validation:
   - `/` works
   - `/check-cik` GET works
   - `/check-cik` POST works (CIK redirect)
   - Smoke tests pass
7. Report: blueprint wiring + verification. **Stop after Milestone 4a.**

**Constraints:**
- Keep URL paths unchanged.
- Do not migrate HTML to templates in this milestone.

---

## Session 5 — Milestone 4b (from `SUMMARY_enhancements_v3.md`): Split routes — `/daily-values`

**Before you start (check prior work):**
- Confirm Milestone 4a blueprint wiring works and tests/smoke pass before adding `/daily-values`.
- If you already migrated `/daily-values`, skip the move and only verify registration + smoke.

**Instructions to agent:**
1. Create `api/pages/daily_values.py`.
2. Copy the full `/daily-values` logic from `api/routes.py` into this module (keep `render_template_string` for now).
3. Register the new blueprint in `api/blueprint.py`.
4. Remove/comment out the original `/daily-values` route from `api/routes.py`.
5. Validation:
   - `/daily-values` loads
   - filters work and query params are preserved
   - smoke tests pass
6. Report and stop after Milestone 4b.

---

## Session 6 — Milestone 4c (from `SUMMARY_enhancements_v3.md`): Split routes — Admin + DB Check

**Before you start (check prior work):**
- Confirm Milestone 2 (`templates/pages/admin.html`) and Milestone 3 (`api/jobs/manager.py`) are complete before migrating admin routes.
- If admin/db-check routes were already moved, avoid re-registering; only reconcile differences and re-run validation.

**Instructions to agent:**
1. Create `api/pages/admin.py`:
   - Use `render_template('pages/admin.html', ...)` (already migrated in M2).
   - Move all `/admin/*` routes into this blueprint (use `url_prefix='/admin'`).
   - Ensure it uses `api.jobs.manager` from M3.
2. Create `api/pages/db_check.py` and migrate `/db-check` and `/sql` (keep `render_template_string` for now; template migration later).
3. Register both blueprints in `api/blueprint.py`.
4. Remove/comment out the corresponding routes from `api/routes.py`.
5. Validation:
   - admin page + job actions work
   - `/db-check` loads
   - `/sql` works
   - smoke tests pass
6. Report and stop after Milestone 4c.

---

## Session 7 — Milestone 5 (from `SUMMARY_enhancements_v3.md`): Services layer for daily values + CIK lookup

**Before you start (check prior work):**
- Confirm pages are already split (Milestones 4a/4b) so you can cleanly move query logic into services.
- If `api/services/daily_values_service.py` exists, refactor toward the plan rather than rewriting.

**Instructions to agent:**
1. Create `api/services/__init__.py`.
2. Create `api/services/daily_values_service.py` and extract:
   - daily-values query building (filters)
   - filter option queries
   - entity lookup by CIK (zero-pad behavior)
3. Update `api/pages/daily_values.py` to call service functions (no query logic in route).
4. Update `api/pages/check_cik.py` to call service function for CIK lookup.
5. Validation:
   - daily-values filters still match prior behavior
   - check-cik redirect still works
   - smoke tests pass
6. Report and stop after Milestone 5.

---

## Session 8 — Milestone 6 (from `SUMMARY_enhancements_v3.md`): `/api/v1` + Pydantic envelope + `/api/v1/admin/jobs`

**Before you start (check prior work):**
- Confirm prior blueprint structure is in place so the v1 blueprint can be registered once.
- If Pydantic is already in `requirements.txt`, do not add a duplicate pin; just install/verify.

**Instructions to agent:**
1. Ensure dependencies are handled:
   - If Pydantic is not installed, add it to requirements appropriately and install.
2. Create schemas:
   - `api/schemas/__init__.py`
   - `api/schemas/api_responses.py` with standard envelope models
3. Create v1 API:
   - `api/api_v1/__init__.py`
   - `api/api_v1/blueprint.py` with `url_prefix='/api/v1'`
   - `api/api_v1/admin.py` with `GET /api/v1/admin/jobs`
4. Register `api_v1` blueprint from the main blueprint factory.
5. Validation:
   - `curl /api/v1/admin/jobs` returns `{ ok, data, error, meta }`
   - error responses use same envelope
   - smoke tests pass
6. Report and stop after Milestone 6.

---

## Session 9 — Milestone 7 (from `SUMMARY_enhancements_v3.md`) (Optional): Live admin polling via `/api/v1/admin/jobs`

**Before you start (check prior work):**
- Confirm Milestone 6 endpoint (`GET /api/v1/admin/jobs`) exists and returns the envelope before adding polling.
- If `static/js/admin.js` already contains polling logic, verify behavior and adjust interval/DOM hooks rather than duplicating.

**Instructions to agent:**
1. Update `static/js/admin.js` to poll `/api/v1/admin/jobs` every N seconds.
2. Add stable DOM hooks to `templates/pages/admin.html` (ids/classes) so JS can update status.
3. Add any small CSS needed to `static/css/components.css`.
4. Validation:
   - admin status updates without refresh
   - no console errors
   - page still usable with JS disabled
   - smoke tests pass
5. Report and stop.

---

## Session 10 — Milestone 8 (from `SUMMARY_enhancements_v3.md`): Security hardening + config + error templates

**Before you start (check prior work):**
- Confirm template/static scaffolding exists (Milestone 1) before creating error templates.
- If you already have an app factory or config module, adapt it—avoid introducing a second configuration path.

**Instructions to agent:**
1. Create `config.py` with feature flags (enable/disable admin/db-check) and logging config.
2. Update `app.py` to use an app factory style (`create_app()`), load config, configure logging, and register error handlers.
3. Create error templates:
   - `templates/errors/404.html`
   - `templates/errors/500.html`
4. Wire error handlers to use templates.
5. Ensure blueprint registration respects `ENABLE_ADMIN` and `ENABLE_DB_CHECK` flags.
6. Create `.env.example`.
7. Validation:
   - With `ENABLE_ADMIN=False`, `/admin` is not reachable
   - With default config, smoke tests pass
8. Report and stop.

---

## Session 11 — Milestone 9a (from `SUMMARY_enhancements_v3.md`): Migrate Home to template

**Before you start (check prior work):**
- Confirm `templates/base.html` exists (Milestone 1).
- If `templates/pages/home.html` already exists, update in-place and keep route behavior unchanged.

**Instructions to agent:**
1. Create/replace `templates/pages/home.html` with the real extracted HTML.
2. Update `api/pages/home.py` to use `render_template('pages/home.html')`.
3. Validation: `/` loads and smoke tests pass.
4. Report and stop.

---

## Session 12 — Milestone 9b (from `SUMMARY_enhancements_v3.md`): Migrate Check CIK to template

**Before you start (check prior work):**
- Confirm Milestone 9a is complete (base template + home migrated) and app still passes smoke tests.
- If `templates/pages/check_cik.html` already exists, reconcile fields/messages rather than overwriting blindly.

**Instructions to agent:**
1. Create `templates/pages/check_cik.html` with the extracted form + any messages/errors.
2. Update `api/pages/check_cik.py` to `render_template(...)`.
3. Validation: GET + POST + redirect works; smoke tests pass.
4. Report and stop.

---

## Session 13 — Milestone 9c (from `SUMMARY_enhancements_v3.md`): Migrate Daily Values to template (+ JS if needed)

**Before you start (check prior work):**
- Confirm Milestone 4b/5 logic is stable before changing rendering.
- If `static/js/daily_values.js` already exists, move only missing inline JS and keep behavior matching existing page.

**Instructions to agent:**
1. Create `templates/pages/daily_values.html` covering:
   - filter form
   - results table
   - preserving filter selections
2. Move any inline JS into `static/js/daily_values.js` and load via template block.
3. Update `api/pages/daily_values.py` to use `render_template(...)`.
4. Validation: filters, preserved params, results render; smoke tests pass.
5. Report and stop.

---

## Session 14 — Milestone 9d (from `SUMMARY_enhancements_v3.md`): Migrate DB Check to template

**Before you start (check prior work):**
- Confirm Milestone 4c migrated `/db-check` into its own page module (or note if still in `api/routes.py`).
- If `templates/pages/db_check.html` already exists, update in-place while preserving form/action URLs.

**Instructions to agent:**
1. Create `templates/pages/db_check.html` from extracted HTML.
2. Update `api/pages/db_check.py` to use `render_template(...)`.
3. Validation: `/db-check` and `/sql` work; smoke tests pass.
4. Report and stop.
