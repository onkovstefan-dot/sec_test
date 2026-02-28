# Flask Refactor Plan - AI Agent Implementation Guide

> **Purpose**: This document guides an AI agent through a systematic refactor of a Flask application from a monolithic routes file to a modular, maintainable architecture with proper separation of concerns.

---

## 🎯 Quick Context

**Current State:**
- Single `api/routes.py` file (~886 lines) with inline HTML/CSS/JS
- Background job management mixed with route handlers
- No template inheritance or static asset management
- Ad-hoc JSON responses without schemas

**Target State:**
- Modular blueprint-based architecture
- Jinja2 templates with inheritance
- Separate static assets (CSS/JS)
- Service layer for business logic
- Versioned JSON API with Pydantic schemas
- Background job manager module

**Constraints:**
- App must remain functional after each milestone
- No "big bang" rewrites - incremental changes only
- Preserve all existing URLs and behavior
- Keep frontend server-rendered (no SPA)
- SQLite database location stays at `data/sec.db`

---

## 📋 Pre-Implementation Checklist

Before starting any milestone, verify:

1. **Read existing code first:**
   - `api/routes.py` - understand all routes and their behavior
   - `app.py` - understand Flask app initialization
   - `models/*.py` - understand data models
   - `utils/*.py` - understand utility functions

2. **Test baseline:**
   - Run existing tests: `pytest pytests/`
   - Manually verify all routes work (see smoke test list below)

3. **Identify inline content:**
   - Search for `render_template_string` calls
   - Find inline `<style>` and `<script>` blocks
   - Note background job management code

---

## 🧪 Smoke Test Checklist

Test these routes after EVERY milestone:

```bash
# Start the app
python app.py

# Test in browser or with curl:
- [ ] GET /                    # Home page loads
- [ ] GET /check-cik           # CIK check form loads
- [ ] POST /check-cik          # CIK redirect works (test with valid CIK)
- [ ] GET /daily-values        # Daily values page renders
- [ ] GET /daily-values?...    # Filters work (entity_id, value_names, etc.)
- [ ] GET /admin               # Admin page loads
- [ ] POST /admin/populate-daily-values  # Job can start (with confirmation token)
- [ ] GET /admin/populate-daily-values   # Job status displays
- [ ] POST /admin/recreate-db  # DB recreate works (with confirmation token)
- [ ] GET /db-check            # DB check page loads
```

**Critical**: If any smoke test fails after a milestone, stop and fix before proceeding.

---

## 📁 Target Folder Structure

```
sec_test/
├── app.py                          # Flask app initialization (MODIFIED)
├── api/
│   ├── __init__.py                 # Existing
│   ├── routes.py                   # DEPRECATED - will be empty or removed
│   ├── blueprint.py                # NEW - main blueprint registration
│   ├── pages/                      # NEW - HTML-returning routes
│   │   ├── __init__.py
│   │   ├── home.py                 # GET /
│   │   ├── check_cik.py            # GET/POST /check-cik
│   │   ├── daily_values.py         # GET /daily-values
│   │   ├── admin.py                # GET/POST /admin/*
│   │   └── db_check.py             # GET /db-check, /sql
│   ├── api_v1/                     # NEW - JSON API routes
│   │   ├── __init__.py
│   │   ├── blueprint.py            # /api/v1 blueprint
│   │   └── admin.py                # GET /api/v1/admin/jobs
│   ├── jobs/                       # NEW - background job management
│   │   ├── __init__.py
│   │   └── manager.py              # Job state and control functions
│   ├── services/                   # NEW - business logic
│   │   ├── __init__.py
│   │   └── daily_values_service.py # Query building for daily values
│   └── schemas/                    # NEW - Pydantic models
│       ├── __init__.py
│       └── api_responses.py        # Standard response envelopes
├── templates/                      # NEW directory
│   ├── base.html                   # Base template with blocks
│   ├── components/
│   │   ├── navbar.html
│   │   └── flash.html
│   └── pages/
│       ├── home.html
│       ├── check_cik.html
│       ├── daily_values.html
│       ├── admin.html
│       └── db_check.html
├── static/                         # NEW directory
│   ├── css/
│   │   ├── app.css                 # Global styles
│   │   └── components.css          # Component styles
│   └── js/
│       ├── admin.js                # Admin page interactivity
│       └── daily_values.js         # Daily values page interactivity
└── ... (existing files unchanged)
```

---

## 🚀 Implementation Milestones

### Milestone 0: Baseline Documentation & Tests

**Goal**: Establish safety net before refactoring.

**Actions:**
1. **Create smoke test document**: `docs/SMOKE_TEST.md` with the checklist above
2. **Verify current functionality**: Run through all smoke tests manually
3. **Document current routes**: Create a quick reference of all existing routes in `api/routes.py`
4. **Check existing tests**: Run `pytest pytests/` and ensure they pass

**Validation:**
- [ ] All smoke tests pass
- [ ] Existing pytest tests pass
- [ ] Documentation created

**No code changes in this milestone.**

---

### Milestone 1: Template & Static Infrastructure

**Goal**: Create folder structure and base templates WITHOUT changing existing routes.

**Actions:**

1. **Create directories:**
   ```bash
   mkdir -p templates/pages templates/components
   mkdir -p static/css static/js
   ```

2. **Create `templates/base.html`:**
   - Include `<head>` with title block
   - Link to `static/css/app.css` using `url_for('static', filename='css/app.css')`
   - Define blocks: `{% block head %}`, `{% block content %}`, `{% block scripts %}`
   - Add basic HTML5 structure with proper charset and viewport

3. **Create `static/css/app.css`:**
   - Start with minimal global styles (body, container, form, table, button)
   - Extract common CSS patterns you'll need (see existing inline styles in routes.py)

4. **Create `static/css/components.css`:**
   - Styles for reusable components (cards, alerts, buttons, forms)

5. **Create empty placeholder templates:**
   - `templates/pages/home.html`
   - `templates/pages/check_cik.html`
   - `templates/pages/daily_values.html`
   - `templates/pages/admin.html`
   - `templates/pages/db_check.html`
   
   Each should contain:
   ```jinja2
   {% extends 'base.html' %}
   {% block content %}
   <!-- Placeholder - to be filled in next milestone -->
   {% endblock %}
   ```

6. **Create empty JS files:**
   - `static/js/admin.js`
   - `static/js/daily_values.js`

**Validation:**
- [ ] Folders created
- [ ] Base template has proper structure
- [ ] CSS files exist (can be minimal)
- [ ] Placeholder templates extend base.html
- [ ] All smoke tests still pass (no routes changed yet)

**Key Implementation Notes:**
- Do NOT modify `api/routes.py` yet
- Do NOT modify `app.py` yet
- Focus only on file creation
- Test that static files are accessible: `http://localhost:5000/static/css/app.css`

---

### Milestone 2: Migrate `/admin` Route to Templates

**Goal**: First real page migration - establish the pattern.

**Actions:**

1. **Extract HTML from `/admin` route in `api/routes.py`:**
   - Find the `render_template_string` call for `/admin`
   - Copy the HTML structure to `templates/pages/admin.html`
   - Convert inline variables to Jinja2 syntax

2. **Extract inline CSS:**
   - Find `<style>` blocks in the admin HTML
   - Move to `static/css/app.css` or create `static/css/admin.css`
   - Remove inline `<style>` tags from template

3. **Extract inline JavaScript:**
   - Find `<script>` blocks in the admin HTML
   - Move to `static/js/admin.js`
   - Load script in template using `{% block scripts %}`
   - Ensure any dynamic values (like CSRF tokens) are passed correctly

4. **Update route handler:**
   ```python
   # Change from:
   return render_template_string(html_string, var1=val1, var2=val2)
   
   # To:
   return render_template('pages/admin.html', var1=val1, var2=val2)
   ```

5. **Test thoroughly:**
   - Admin page displays correctly
   - CSS styles apply
   - JavaScript functions work
   - Form submissions work (populate job, recreate DB)
   - Confirmation tokens still validate

**Validation:**
- [ ] `/admin` uses `render_template()` instead of `render_template_string()`
- [ ] No inline CSS in admin.html
- [ ] No inline JavaScript in admin.html
- [ ] All admin functionality works (start/stop jobs, view status)
- [ ] All smoke tests pass

**Key Implementation Notes:**
- Keep the same context variables passed to template
- Preserve form structure exactly (especially hidden confirmation tokens)
- Test both GET and POST requests
- Check that background job status updates still display

---

### Milestone 3: Extract Background Job Management

**Goal**: Separate job logic from route handlers.

**Actions:**

1. **Create `api/jobs/__init__.py`** (empty or with module docstring)

2. **Create `api/jobs/manager.py`:**
   
   Move these from `api/routes.py`:
   - `_populate_job_lock`, `_populate_job_state` → PopulateJobManager class
   - `_recreate_job_lock`, `_recreate_job_state` → RecreateJobManager class
   - `_start_populate_daily_values_background()` → method
   - `_start_recreate_db_background()` → method
   - `_read_last_log_line()` → utility function

   Example structure:
   ```python
   class PopulateJobManager:
       def __init__(self):
           self.lock = threading.Lock()
           self.state = {"running": False, "started_at": None, ...}
       
       def start(self) -> bool:
           """Start populate job. Returns True if started, False if already running."""
           ...
       
       def stop(self):
           """Request cooperative stop."""
           ...
       
       def get_status(self) -> dict:
           """Return current job status."""
           ...
       
       def get_last_log_line(self) -> str:
           """Read last line from populate log."""
           ...
   
   # Singleton instances
   populate_job_manager = PopulateJobManager()
   recreate_job_manager = RecreateJobManager()
   ```

3. **Update `api/routes.py` (or `api/pages/admin.py` if already split):**
   - Import job managers
   - Replace direct state access with manager methods
   - Simplify route handlers to thin controllers

**Validation:**
- [ ] Job manager module exists
- [ ] All job functionality works through manager
- [ ] Route handlers are simplified
- [ ] All smoke tests pass (especially admin job control)

**Key Implementation Notes:**
- Keep the same locking behavior (thread-safe)
- Preserve log file paths and reading logic
- Don't change background thread implementation yet (just organize it)
- Ensure managers are importable from routes

---

### Milestone 4: Split Routes into Blueprint Modules

**Goal**: Break up monolithic `api/routes.py` into logical modules.

**Actions:**

1. **Create blueprint registration file `api/blueprint.py`:**
   ```python
   from flask import Blueprint
   
   def create_api_blueprint():
       api_bp = Blueprint("api", __name__)
       
       # Register sub-blueprints (will add in steps below)
       from .pages import home, check_cik, daily_values, admin, db_check
       
       api_bp.register_blueprint(home.bp)
       api_bp.register_blueprint(check_cik.bp)
       api_bp.register_blueprint(daily_values.bp)
       api_bp.register_blueprint(admin.bp)
       api_bp.register_blueprint(db_check.bp)
       
       return api_bp
   ```

2. **Create `api/pages/__init__.py`** (empty)

3. **Create individual route modules** (one at a time):

   **a. `api/pages/home.py`:**
   - Move `/` route from `api/routes.py`
   - Create blueprint: `bp = Blueprint('home', __name__)`
   - Route decorator: `@bp.route('/')`

   **b. `api/pages/check_cik.py`:**
   - Move `/check-cik` routes (GET and POST)
   - Create blueprint: `bp = Blueprint('check_cik', __name__)`

   **c. `api/pages/daily_values.py`:**
   - Move `/daily-values` route
   - Include all query building logic initially
   - Create blueprint: `bp = Blueprint('daily_values', __name__)`

   **d. `api/pages/admin.py`:**
   - Move all `/admin*` routes
   - Import job managers from `api.jobs.manager`
   - Create blueprint: `bp = Blueprint('admin', __name__)`

   **e. `api/pages/db_check.py`:**
   - Move `/db-check` and `/sql` routes
   - Create blueprint: `bp = Blueprint('db_check', __name__)`

4. **Update `app.py`:**
   ```python
   from api.blueprint import create_api_blueprint
   
   app = Flask(__name__)
   api_bp = create_api_blueprint()
   app.register_blueprint(api_bp)
   ```

5. **Deprecate old routes file:**
   - Keep `api/routes.py` temporarily for reference
   - Or delete it once all routes are migrated

**Validation:**
- [ ] All routes accessible at original URLs
- [ ] Each page module has its own blueprint
- [ ] `app.py` uses new blueprint structure
- [ ] All smoke tests pass
- [ ] No errors in Flask startup logs

**Key Implementation Notes:**
- Migrate ONE route module at a time, testing after each
- Preserve exact URL patterns (use `@bp.route()` with same paths)
- Keep all imports in each module (DB models, utils, etc.)
- URL generation with `url_for()` may need blueprint prefix: `url_for('check_cik.check_cik')`

---

### Milestone 5: Create Services Layer

**Goal**: Extract business logic from route handlers.

**Actions:**

1. **Create `api/services/__init__.py`** (empty)

2. **Create `api/services/daily_values_service.py`:**
   
   Extract query building logic from `api/pages/daily_values.py`:
   
   ```python
   from typing import List, Optional
   from sqlalchemy.orm import Session
   from models.daily_values import DailyValue
   from models.entities import Entity
   from models.value_names import ValueName
   # ... other imports
   
   def build_daily_values_query(
       session: Session,
       entity_id: Optional[int] = None,
       value_name_ids: Optional[List[int]] = None,
       unit: Optional[str] = None,
       start_date: Optional[str] = None,
       end_date: Optional[str] = None,
       limit: int = 100
   ):
       """Build filtered query for daily values."""
       query = session.query(DailyValue)
       
       if entity_id:
           query = query.filter(DailyValue.entity_id == entity_id)
       
       if value_name_ids:
           query = query.filter(DailyValue.value_name_id.in_(value_name_ids))
       
       # ... more filters
       
       return query.limit(limit)
   
   def get_filter_options(session: Session):
       """Get distinct values for filter dropdowns."""
       return {
           'entities': session.query(Entity).all(),
           'value_names': session.query(ValueName).all(),
           'units': session.query(DailyValue.unit).distinct().all()
       }
   ```

3. **Update `api/pages/daily_values.py`:**
   - Import service functions
   - Replace inline query building with service calls
   - Keep route handler focused on request/response

4. **Repeat for other complex pages if needed:**
   - Consider `api/services/entity_service.py` for entity lookups
   - Services should be pure business logic (no Flask request/response)

**Validation:**
- [ ] Daily values page works identically
- [ ] All filters function correctly
- [ ] Service functions are reusable (not tied to Flask)
- [ ] All smoke tests pass

**Key Implementation Notes:**
- Services should accept plain Python types, not Flask request objects
- Services should return data, not Flask responses
- Keep database session management in routes (pass session to service)
- Services should be testable without Flask app context

---

### Milestone 6: Create `/api/v1` JSON Endpoints

**Goal**: Establish versioned JSON API with standard response format.

**Actions:**

1. **Create `api/schemas/__init__.py`** and `api/schemas/api_responses.py`:**
   
   ```python
   from typing import Optional, Any
   from pydantic import BaseModel
   
   class APIResponse(BaseModel):
       ok: bool
       data: Optional[Any] = None
       error: Optional[dict] = None
       meta: Optional[dict] = None
   
   class ErrorDetail(BaseModel):
       code: str
       message: str
       details: Optional[dict] = None
   ```

2. **Create `api/api_v1/__init__.py`** (empty)

3. **Create `api/api_v1/blueprint.py`:**
   ```python
   from flask import Blueprint
   
   def create_api_v1_blueprint():
       api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')
       
       # Register v1 endpoints
       from . import admin
       api_v1_bp.register_blueprint(admin.bp)
       
       return api_v1_bp
   ```

4. **Create `api/api_v1/admin.py`:**
   
   ```python
   from flask import Blueprint, jsonify
   from api.jobs.manager import populate_job_manager, recreate_job_manager
   from api.schemas.api_responses import APIResponse
   
   bp = Blueprint('admin_api', __name__, url_prefix='/admin')
   
   @bp.route('/jobs', methods=['GET'])
   def get_jobs_status():
       """Get status of all background jobs."""
       try:
           data = {
               'populate': populate_job_manager.get_status(),
               'recreate': recreate_job_manager.get_status()
           }
           response = APIResponse(ok=True, data=data)
           return jsonify(response.dict())
       except Exception as e:
           response = APIResponse(
               ok=False,
               error={'code': 'SERVER_ERROR', 'message': str(e)}
           )
           return jsonify(response.dict()), 500
   ```

5. **Update `api/blueprint.py` to register v1 API:**
   ```python
   from .api_v1.blueprint import create_api_v1_blueprint
   
   def create_api_blueprint():
       # ... existing page blueprints
       
       # Register API v1
       api_v1_bp = create_api_v1_blueprint()
       api_bp.register_blueprint(api_v1_bp)
       
       return api_bp
   ```

6. **Test new endpoint:**
   ```bash
   curl http://localhost:5000/api/v1/admin/jobs
   ```
   
   Should return:
   ```json
   {
     "ok": true,
     "data": {
       "populate": {"running": false, ...},
       "recreate": {"running": false, ...}
     },
     "error": null,
     "meta": null
   }
   ```

**Validation:**
- [ ] `/api/v1/admin/jobs` returns JSON with standard envelope
- [ ] Pydantic models validate responses
- [ ] Error responses follow same format
- [ ] All smoke tests still pass

**Key Implementation Notes:**
- Start with ONE endpoint to establish pattern
- Always return standard envelope (even for errors)
- Use proper HTTP status codes (200, 400, 404, 500)
- Don't break existing HTML routes

---

### Milestone 7: Enhance Admin with Live Updates (Optional)

**Goal**: Make admin page more responsive using `/api/v1` endpoints.

**Actions:**

1. **Update `static/js/admin.js`:**
   
   ```javascript
   // Poll job status every 5 seconds
   async function updateJobStatus() {
       try {
           const response = await fetch('/api/v1/admin/jobs');
           const result = await response.json();
           
           if (result.ok) {
               // Update populate job status
               updateStatusBlock('populate-status', result.data.populate);
               
               // Update recreate job status
               updateStatusBlock('recreate-status', result.data.recreate);
           }
       } catch (error) {
           console.error('Failed to fetch job status:', error);
       }
   }
   
   function updateStatusBlock(elementId, jobData) {
       const element = document.getElementById(elementId);
       if (!element) return;
       
       element.querySelector('.running').textContent = jobData.running ? 'Yes' : 'No';
       element.querySelector('.last-log').textContent = jobData.last_log_line || 'N/A';
       // ... update other fields
   }
   
   // Start polling when page loads
   setInterval(updateJobStatus, 5000);
   updateJobStatus(); // Initial load
   ```

2. **Update `templates/pages/admin.html`:**
   - Add ID attributes to status display elements
   - Keep server-rendered content as fallback
   - Add loading indicators

**Validation:**
- [ ] Admin page updates without refresh
- [ ] Status changes reflect in real-time
- [ ] Page still works with JavaScript disabled (server-rendered fallback)
- [ ] No console errors

**Key Implementation Notes:**
- This is optional - can be done later
- Polling is simple but sufficient for admin pages
- Keep server-rendered version as fallback
- Consider adding a "last updated" timestamp

---

### Milestone 8: Security Hardening

**Goal**: Add basic security measures before production use.

**Actions:**

1. **Create `config.py` for environment-based settings:**
   ```python
   import os
   
   class Config:
       DEBUG = os.getenv('FLASK_DEBUG', 'False') == 'True'
       ENABLE_ADMIN = os.getenv('ENABLE_ADMIN', 'True') == 'True'
       ENABLE_DB_CHECK = os.getenv('ENABLE_DB_CHECK', 'False') == 'True'
       SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
   ```

2. **Update `app.py`:**
   ```python
   from config import Config
   
   app.config.from_object(Config)
   ```

3. **Add conditional route registration:**
   ```python
   # In api/blueprint.py
   def create_api_blueprint():
       api_bp = Blueprint("api", __name__)
       
       # Always register
       api_bp.register_blueprint(home.bp)
       api_bp.register_blueprint(check_cik.bp)
       api_bp.register_blueprint(daily_values.bp)
       
       # Conditional registration
       from flask import current_app
       if current_app.config.get('ENABLE_ADMIN', True):
           api_bp.register_blueprint(admin.bp)
       
       if current_app.config.get('ENABLE_DB_CHECK', False):
           api_bp.register_blueprint(db_check.bp)
       
       return api_bp
   ```

4. **Add input validation:**
   - Validate entity_id is integer
   - Validate date formats
   - Sanitize SQL query inputs (already using SQLAlchemy, good)

5. **Add error handlers to `app.py`:**
   ```python
   @app.errorhandler(404)
   def not_found(e):
       return render_template('errors/404.html'), 404
   
   @app.errorhandler(500)
   def server_error(e):
       # Log full error server-side
       app.logger.error(f'Server Error: {e}')
       # Show friendly message to user
       return render_template('errors/500.html'), 500
   ```

6. **Add basic request logging:**
   ```python
   @app.before_request
   def log_request():
       app.logger.info(f'{request.method} {request.path}')
   ```

**Validation:**
- [ ] Config-based feature flags work
- [ ] Dangerous routes can be disabled
- [ ] Error pages display properly
- [ ] Logging captures requests
- [ ] All smoke tests pass

**Key Implementation Notes:**
- Don't implement full authentication yet (JWT is Milestone 10+)
- Focus on defense-in-depth: disable dangerous routes by default
- Log errors but don't expose internals to users
- SECRET_KEY should be random in production

---

### Milestone 9: Migrate Remaining Routes to Templates

**Goal**: Complete template migration for all pages.

**Actions:**

1. **Migrate `/` (home page):**
   - Create `templates/pages/home.html`
   - Extract any inline HTML/CSS/JS
   - Update `api/pages/home.py` to use `render_template()`

2. **Migrate `/check-cik`:**
   - Create `templates/pages/check_cik.html`
   - Move form HTML and styles to template/CSS
   - Update `api/pages/check_cik.py`

3. **Migrate `/daily-values`:**
   - Create `templates/pages/daily_values.html`
   - Move table rendering, filter forms to template
   - Extract any JavaScript to `static/js/daily_values.js`
   - Update `api/pages/daily_values.py`

4. **Migrate `/db-check`:**
   - Create `templates/pages/db_check.html`
   - Move SQL query form and results display
   - Update `api/pages/db_check.py`

5. **Remove `render_template_string` completely:**
   - Search codebase for any remaining uses
   - Convert to proper templates

**Validation:**
- [ ] All pages use `render_template()`
- [ ] No `render_template_string()` calls remain
- [ ] All inline CSS moved to static files
- [ ] All inline JS moved to static files
- [ ] All smoke tests pass

**Key Implementation Notes:**
- Do one page at a time
- Test each page thoroughly after migration
- Check that all forms still submit correctly
- Verify JavaScript functions work
- Ensure filters and query parameters are preserved

---

## 🔄 Post-Migration Tasks

After all milestones are complete:

1. **Code cleanup:**
   - Remove deprecated `api/routes.py` if not already done
   - Remove any dead code or unused imports
   - Run linter/formatter (black, flake8)

2. **Documentation updates:**
   - Update README.md with new architecture
   - Document blueprint structure
   - Add API documentation for `/api/v1` endpoints
   - Update development setup instructions

3. **Test coverage:**
   - Add unit tests for service layer
   - Add integration tests for API endpoints
   - Add tests for job manager

4. **Performance check:**
   - Verify no performance regression
   - Check database query efficiency
   - Profile background jobs if needed

---

## 🎓 Key Principles for AI Agent

### 1. Read Before Writing
Always read the target file completely before making changes. Use `read_file` tool.

### 2. Preserve Behavior
Never change functionality while refactoring. URLs, responses, and behavior must remain identical.

### 3. One Change at a Time
Complete one milestone fully before starting the next. Test after each change.

### 4. Test Frequently
Run smoke tests after every significant change. If tests fail, fix immediately before proceeding.

### 5. Keep Context
When moving code between files, ensure all imports and dependencies move correctly.

### 6. Document Decisions
When making architectural choices, note them in code comments.

### 7. Extract, Don't Rewrite
When moving inline HTML to templates, extract the existing HTML first, then improve it in a separate step.

### 8. Validate Imports
After creating new modules, verify imports work:
```python
from api.jobs.manager import populate_job_manager  # Will this work?
```

### 9. Check File Paths
Ensure template and static file paths are correct:
```python
render_template('pages/admin.html')  # Not 'templates/pages/admin.html'
url_for('static', filename='css/app.css')  # Correct path
```

### 10. Use Tools
- `semantic_search`: Find similar code patterns
- `list_code_usages`: See how functions are called
- `grep_search`: Find specific strings
- `get_errors`: Check for syntax errors after editing

---

## 🚨 Common Pitfalls to Avoid

1. **Breaking URLs**: Always preserve exact URL patterns. Users may have bookmarks.

2. **Losing Request Context**: When extracting to services, don't pass `request` object. Extract values first.

3. **Template Path Errors**: Flask looks in `templates/` directory by default. Don't include "templates/" in path.

4. **Static File 404s**: Ensure static files are in `static/` directory and app knows about it.

5. **Blueprint Naming Conflicts**: Give each blueprint a unique name.

6. **Circular Imports**: Be careful when blueprints import from each other. Use factory pattern if needed.

7. **Database Session Management**: Don't forget to close sessions. Use context managers.

8. **Background Job Races**: Preserve thread safety when moving job management code.

9. **Missing Template Variables**: Ensure all variables used in templates are passed in context.

10. **JavaScript Path Issues**: Use `url_for()` in templates for all asset URLs, not hardcoded paths.

---

## 📚 Reference: Current Route Structure

Before refactoring, document the current routes. Example:

```
GET  /                          → Home page
GET  /check-cik                 → CIK lookup form
POST /check-cik                 → Process CIK, redirect to daily-values
GET  /daily-values              → Display daily values with filters
GET  /admin                     → Admin dashboard
POST /admin/populate-daily-values  → Start populate job
GET  /admin/populate-daily-values  → Get populate job status
POST /admin/stop-populate       → Stop populate job
POST /admin/recreate-db         → Start recreate DB job
GET  /admin/recreate-db         → Get recreate DB status
GET  /db-check                  → Database inspection page
POST /sql                       → Execute SQL query
```

**Action for agent**: Before starting, generate this list from `api/routes.py`.

---

## 🎯 Success Criteria

The refactor is complete when:

- [ ] No `render_template_string()` calls remain
- [ ] All HTML is in `templates/` directory
- [ ] All CSS is in `static/css/` directory
- [ ] All JS is in `static/js/` directory
- [ ] Routes are split into logical blueprint modules
- [ ] Business logic is in service layer
- [ ] Background jobs managed by dedicated module
- [ ] At least one `/api/v1` endpoint exists with Pydantic schemas
- [ ] All smoke tests pass
- [ ] All existing pytest tests pass
- [ ] No console errors or warnings
- [ ] Documentation updated

---

## 📝 Agent Execution Notes

As an AI agent executing this plan:

1. **Start with Milestone 0**: Don't skip the baseline documentation.

2. **After each file creation/modification**: 
   - Use `get_errors` to check for syntax issues
   - Validate imports and paths
   - Run relevant smoke tests

3. **When extracting code**:
   - Use `read_file` to get full context
   - Use `replace_string_in_file` or `insert_edit_into_file` for changes
   - Verify the extraction with semantic_search

4. **When creating new modules**:
   - Always create `__init__.py` first
   - Import in the correct order (avoid circular imports)
   - Test imports immediately

5. **Progress tracking**:
   - After completing each milestone, note what was accomplished
   - Keep a running list of what's left
   - If stuck, break the current step into smaller substeps

6. **Communication**:
   - Report which milestone you're working on
   - Explain what you're about to do before doing it
   - If you encounter an issue, describe it clearly

---

## 🔮 Future Enhancements (Post-Refactor)

These are NOT part of the current refactoring plan but can be considered later:

1. **JWT Authentication**: Add user authentication and authorization
2. **API Rate Limiting**: Protect endpoints from abuse
3. **Database Migrations**: Use Alembic for schema migrations
4. **Caching**: Add Redis or simple caching for frequently accessed data
5. **Async Routes**: Convert to async views for better performance
6. **WebSocket Support**: Real-time updates for job status (instead of polling)
7. **TypeScript**: Add TypeScript compilation if frontend complexity grows
8. **API Documentation**: Auto-generate docs with Swagger/OpenAPI
9. **Containerization**: Add Dockerfile and docker-compose
10. **CI/CD Pipeline**: Automated testing and deployment

---

## ✅ Quick Start for AI Agent

**To begin execution:**

1. Read this entire document
2. Run `semantic_search` on `api/routes.py` to understand current structure
3. Read `api/routes.py` completely
4. Read `app.py` to understand Flask setup
5. Start with **Milestone 0** - create smoke test document
6. Proceed through milestones sequentially
7. Test after each change
8. Report progress and any issues

**Remember**: Working software at every step is more important than speed. Take your time and test thoroughly.
