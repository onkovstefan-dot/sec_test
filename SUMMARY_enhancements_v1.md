# Enhancements / Refactor Plan

This project has grown beyond a single `api/routes.py`. Below is a concrete refactor plan to improve maintainability, enable template inheritance, keep routes modular, and prepare for a cleaner separation between UI and backend logic.

## Goals

1. Split HTML/JS/CSS out of Python strings.
2. Put each API/page route group into its own module.
3. Introduce template inheritance with a shared header/footer and consistent layout.
4. Keep the current UI behavior while making it easier to evolve.
5. Establish a more robust API contract between frontend and backend.
6. Improve error handling, logging, and user-facing messages.
7. Keep the frontend as static as possible; keep business logic/calculation on the backend.
8. Leave a clear path to add authentication/authorization (JWT) later.

---

## Milestone-based implementation plan

This is an incremental plan designed to keep the app working at every step (no “big bang” rewrite). Each milestone should be a small PR-sized change.

### Milestone 0 — Baseline + guardrails

**Outcome:** you can refactor safely without breaking behavior.

- Add/confirm a quick manual smoke checklist in the README (or a short `docs/SMOKE_TEST.md`):
  - `/` loads
  - `/check-cik` redirect flow works
  - `/daily-values` renders and preserves filters
  - `/admin` loads and can start/stop jobs
- Optional: add a minimal `pytest` scaffold later (not required before template migration).

### Milestone 1 — Template + static scaffolding (no behavior change)

**Outcome:** Jinja + static assets are wired up, but routes can still be inline for now.

- Create `templates/base.html` with `{% block content %}` etc.
- Create `static/css/app.css` (and optionally `static/css/components.css`).
- Create placeholder page templates under `templates/pages/`.
- Ensure pages can load CSS via `url_for('static', ...)`.

### Milestone 2 — Migrate `/admin` from inline HTML to templates/static

**Outcome:** first “real” page moved out of Python strings; establishes the pattern.

- Convert `/admin` route to `render_template('pages/admin.html', ...)`.
- Move inline `<style>` → `static/css/app.css` (or `static/css/admin.css` if you prefer page CSS).
- Move inline `<script>` → `static/js/admin.js`.
- Keep form fields + confirmation token behavior identical.

### Milestone 3 — Extract background job state/logic into `api/jobs/manager.py`

**Outcome:** routes become thin; job logic becomes testable and reusable.

- Create `api/jobs/manager.py`:
  - job start helpers (populate/recreate)
  - cooperative stop state
  - last-log-line helper
  - “ensure schema exists” helper for populate
- Update admin routes to call the manager instead of owning global dicts/locks.
- (Optional) give recreate-db its own logfile so status reflects real output.

### Milestone 4 — Split route modules (pages)

**Outcome:** no more monolithic `api/routes.py`.

- Introduce a blueprint structure:
  - `api/blueprint.py` registers sub-blueprints
  - `api/pages/admin.py`, `home.py`, `check_cik.py`, `daily_values.py`, `db_check.py`
- Move the existing routes one module at a time.
- Keep URLs stable.

### Milestone 5 — Services layer for query building

**Outcome:** business/query logic lives outside route handlers.

- Add `api/services/daily_values_service.py`:
  - build the SQLAlchemy query given `value_names[]`, `unit`, entity selection, etc.
  - compute distinct filter options
- Update `pages/daily_values.py` to call the service.

### Milestone 6 — Introduce `/api/v1` with a small, contracted surface

**Outcome:** a stable JSON API exists for dynamic UI and future clients.

- Create `/api/v1` blueprint.
- Add one endpoint first (smallest useful):
  - `GET /api/v1/admin/jobs` → returns job statuses
- Standardize responses with the `{ ok, data, error, meta }` envelope.
- Add Pydantic schemas for request/response.

### Milestone 7 — Enhance admin UX using `/api/v1` (optional)

**Outcome:** admin page becomes more responsive without becoming a SPA.

- Add polling in `static/js/admin.js`:
  - fetch `/api/v1/admin/jobs` every N seconds
  - update status blocks (running, last log line, timestamps)
- Keep server-rendered fallback for no-JS.

### Milestone 8 — Security hardening (incremental)

**Outcome:** safer defaults before exposing beyond localhost.

- Add a config flag to disable dangerous routes in non-dev (e.g., `ENABLE_ADMIN=0` by default in production).
- Add basic auth gate (simple shared secret) as an interim step if needed.
- Add CSRF protection when the app becomes multi-user or internet-exposed.
- Tighten `/db-check` access (localhost-only or disabled by default).

### Milestone 9 — True interruptible jobs (only if needed)

**Outcome:** “stop” actually stops.

- Replace thread-based job runner with subprocess-based execution.
- Track PIDs and implement stop via terminate/kill.
- Continue streaming stdout/stderr to dedicated log files.

---

## Proposed folder structure

### Option A (recommended): blueprint + templates/static per feature

```
sec_test/
  app.py
  api/
    __init__.py
    blueprint.py              # creates api_bp and registers sub-blueprints
    pages/
      __init__.py
      home.py                 # GET /
      check_cik.py            # GET /check-cik
      daily_values.py         # GET /daily-values
      admin.py                # /admin, /admin/recreate-db, etc.
      db_check.py             # /db-check, /sql
    api_v1/
      __init__.py
      blueprint.py            # /api/v1 blueprint
      daily_values.py         # JSON endpoints (contracted)
      admin.py                # job status endpoints (contracted)
    jobs/
      __init__.py
      manager.py              # background job state + helpers
    services/
      __init__.py
      daily_values_service.py # query building + filtering rules
      entities_service.py
    schemas/
      __init__.py
      daily_values.py         # response/request schemas (Pydantic)
  templates/
    base.html                 # header/footer + blocks
    components/
      navbar.html
      flash.html
    pages/
      home.html
      check_cik.html
      daily_values.html
      admin.html
      db_check.html
  static/
    css/
      app.css
      components.css
    js/
      admin.js
      daily_values.js
```

Notes:
- Keep **HTML pages** and **JSON APIs** separate (`api/pages/*` vs `api/api_v1/*`).
- Keep DB + query logic out of route handlers (`api/services/*`).
- Add explicit request/response schemas (`api/schemas/*`) for a robust contract.

---

## Robust API contract (frontend ↔ backend)

### Why
Right now endpoints return either HTML or ad-hoc JSON. As the UI grows, define a stable JSON contract for programmatic use and to support future UI changes.

### Recommendations

1. Create a versioned API namespace: `/api/v1/...`.
2. Prefer returning JSON in a consistent envelope:

```json
{
  "ok": true,
  "data": { ... },
  "error": null,
  "meta": { ... }
}
```

On errors:

```json
{
  "ok": false,
  "data": null,
  "error": { "code": "VALIDATION_ERROR", "message": "...", "details": {...} },
  "meta": { ... }
}
```

3. Validate inputs and shape outputs using **Pydantic** models (lightweight and common). This provides:
   - typed request params
   - typed responses
   - a single source of truth for the API contract

4. Keep HTML routes server-rendered (Jinja2) initially, but have them optionally consume `/api/v1` endpoints via fetch for dynamic pieces (progress/status tables, autocomplete lists, etc.).

---

## Template handling & UI component strategy

### Use Flask’s built-in Jinja2 templates (recommended)
- Move HTML into `templates/`.
- Use `render_template()` instead of inline f-strings.
- Use `base.html` with `{% block content %}` and `{% block head %}` / `{% block scripts %}`.
- Create reusable components via includes/macros:
  - `templates/components/navbar.html`
  - `templates/components/flash.html`
  - `templates/components/forms.html` (macros)

### Styling: keep it simple but maintainable

Common approaches (in increasing complexity):

1. Single `static/css/app.css` (OK for small apps)
2. Split into `app.css` + `components.css` + page CSS files
3. Add a small utility CSS framework later **only if needed**:
   - Pico.css (very lightweight)
   - Bootstrap (heavier but common)

Recommendation: start with (2) and enforce a naming scheme (BEM or component-prefixed classes).

---

## JavaScript vs TypeScript

### Default: keep JS minimal
Your app can remain mostly server-rendered and avoid heavy frontend complexity.

- Prefer no JS where possible.
- When JS is needed, keep it to small, page-scoped files under `static/js/`.

### TypeScript plan (no npm initially)
If you want TypeScript eventually, treat it as a later phase.

**Phase 1 (recommended now):**
- No npm.
- No bundler/build tool.
- Keep the frontend mostly static (server-rendered templates + minimal plain JS).

**Phase 2 (when you truly need TS):**
- Introduce package management (npm) and add TypeScript compilation.
- Keep the build as small as possible (e.g., `tsc` to compile `static/ts/*.ts` → `static/js/*.js`).

Why postpone TS until npm exists:
- TypeScript requires a compiler; without npm, installs are not reproducible.
- Avoid committing toolchain-specific setup early.

TypeScript benefits once adopted:
- compile-time checking for API response shapes
- fewer runtime UI bugs

If you choose TS later, align it with the `/api/v1` schemas to avoid drift.

---

## Error handling, logging, and user messages

### Backend

1. Centralize error responses:
   - Register Flask error handlers (`@app.errorhandler`) for 400/404/500
   - Ensure JSON endpoints always return the standard error envelope

2. Add a structured logger:
   - Use Python `logging` with a consistent format
   - Log request IDs (generate per request; add to response headers)

3. Avoid leaking internals to users:
   - show friendly error message in UI
   - log full traceback server-side

4. Background jobs:
   - capture stdout/stderr to dedicated log files per job (so “last log line” is meaningful)
   - expose API endpoints for job status: `/api/v1/admin/jobs`

### Frontend (server-rendered + minimal JS)

- Use a simple flash/message pattern in templates:
  - success: “Job started”
  - warning: “Job already running”
  - error: “Failed to start job; see logs”

- For JS-enhanced pages:
  - show non-blocking inline notifications
  - fallback to server-rendered messages if JS disabled

---

## Security & data privacy (frontend + backend)

### Keep frontend mostly static
- Use server-rendered templates.
- Keep calculations and business rules in backend services.
- Frontend JS should only:
  - submit forms
  - render results provided by the backend
  - poll a status endpoint

### Backend hardening checklist

1. Input validation:
   - validate query params (entity_id, filters)
   - validate admin form inputs (already doing confirm tokens)

2. Limit dangerous endpoints:
   - protect admin endpoints (see JWT plan below)
   - add rate-limits later if exposed beyond localhost

3. Avoid exposing sensitive data:
   - do not return full DB rows by default
   - ensure `/db-check` is not publicly exposed in production

4. SQLite considerations:
   - treat the DB file as sensitive local data
   - avoid returning file paths or stack traces in responses

5. CSRF protection (when you add auth / non-local usage):
   - consider Flask-WTF or custom CSRF token

---

## JWT authentication (future)

Not needed for local dev, but plan for it:

1. Add an auth blueprint: `/api/v1/auth`
2. Use short-lived access tokens (JWT) and refresh tokens (optional)
3. On the HTML side:
   - store JWT in an **HttpOnly cookie** (avoid localStorage)
4. Add role/permission checks:
   - admin-only routes (`/admin`, `/api/v1/admin/*`)

Suggested libraries (later):
- `PyJWT` (low-level)
- `flask-jwt-extended` (higher-level)

---

## Route modularization

### One route module per page / endpoint group

Recommended grouping:

- `pages/home.py`: `/`
- `pages/check_cik.py`: `/check-cik`
- `pages/daily_values.py`: `/daily-values`
- `pages/admin.py`: `/admin`, etc.
- `pages/db_check.py`: `/db-check`, `/sql`

And JSON APIs:
- `api_v1/daily_values.py`: `/api/v1/daily-values`
- `api_v1/admin.py`: `/api/v1/admin/jobs`, `/api/v1/admin/jobs/<id>`

---

## Background job code organization

Move in-process background job state out of `routes.py`:

- `api/jobs/manager.py`
  - start/stop helpers
  - job state
  - log tail helper
  - (optional) switch to subprocess-based jobs for true stop support

Then `pages/admin.py` and `api_v1/admin.py` call into that module.

---

## Migration checklist

1. Create `templates/base.html` + `static/css/app.css`.
2. Convert one page first (recommend `/admin`) to `render_template()`.
3. Move inline JS to `static/js/admin.js` (or `static/ts/admin.ts` if adopting TS).
4. Split admin routes + job logic into separate modules (`pages/admin.py`, `jobs/manager.py`).
5. Introduce `/api/v1` endpoints for job status and daily values.
6. Add Pydantic schemas for your first endpoint.
7. Repeat for `/check-cik`, `/daily-values`, `/db-check`.
8. Add auth (JWT) only after API v1 shapes are stable.

---

## Startup scaffolding (templates + static files)

This section lists the minimal files to create early so you can immediately start removing inline HTML/CSS/JS from Python.

### 1) Base template + shared layout

Create:

- `templates/base.html`
  - includes shared `<head>` (title placeholder, CSS link)
  - includes standard header + footer
  - defines blocks:
    - `{% block head %}{% endblock %}`
    - `{% block content %}{% endblock %}`
    - `{% block scripts %}{% endblock %}`

Create optional shared components:

- `templates/components/navbar.html`
- `templates/components/flash.html`

### 2) Page templates

Create initial page templates (even as simple placeholders) so you can migrate one page at a time:

- `templates/pages/home.html`
- `templates/pages/check_cik.html`
- `templates/pages/daily_values.html`
- `templates/pages/admin.html`
- `templates/pages/db_check.html`

Each should start with:

- `{% extends 'base.html' %}`
- a `{% block content %}` section

### 3) Shared CSS

Create:

- `static/css/app.css` (global styles)
- `static/css/components.css` (optional; reusable UI component styles)

Link CSS in `base.html` using:

- `{{ url_for('static', filename='css/app.css') }}`

### 4) JavaScript / TypeScript startup (no npm initially)

**Phase 1 (no npm):** use plain JavaScript files only.

Create:

- `static/js/admin.js`
- `static/js/daily_values.js`

Load scripts from templates via `{% block scripts %}` with:

- `<script defer src="{{ url_for('static', filename='js/admin.js') }}"></script>`

**Phase 2 (when npm is introduced):** add TypeScript sources and compilation.

Create:

- `static/ts/admin.ts`
- `static/ts/daily_values.ts`

Compile to:

- `static/js/admin.js`
- `static/js/daily_values.js`

Important: without a TS compiler step, browsers cannot run `.ts` files directly. Until npm/`tsc` exists, keep runtime scripts in `static/js/`.
