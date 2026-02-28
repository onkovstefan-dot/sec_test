# Flask Refactor Plan - AI Agent Implementation Guide (Session-Optimized)

> **Purpose**: This document guides an AI agent through a systematic refactor of a Flask application. Each milestone is designed to be completed in ONE agent session (~20-40 minutes).

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

## 📋 Session Start Protocol

**At the start of EACH session, the agent should:**

1. **Read this plan**: Understand the full context
2. **Identify current milestone**: Based on what's completed
3. **Read the milestone instructions**: Understand the specific tasks
4. **Gather context**: Read relevant existing files
5. **Execute the milestone**: Complete all tasks
6. **Validate**: Run smoke tests and verify completion
7. **Report status**: Summarize what was accomplished

---

## 🧪 Smoke Test Checklist

**Run these after EVERY milestone:**

```bash
# Start the app (in terminal)
python app.py

# Test in browser or with curl:
✓ GET /                    # Home page loads
✓ GET /check-cik           # CIK check form loads
✓ POST /check-cik          # CIK redirect works (test with CIK: 0001318605)
✓ GET /daily-values        # Daily values page renders
✓ GET /daily-values?entity_id=1  # Filters work
✓ GET /admin               # Admin page loads
✓ POST /admin/populate-daily-values  # Job can start
✓ GET /admin/populate-daily-values   # Job status displays
✓ POST /admin/recreate-db  # DB recreate works
✓ GET /db-check            # DB check page loads
```

**If ANY test fails, STOP and fix before proceeding.**

---

## 📁 Target Folder Structure

```
sec_test/
├── app.py                          # MODIFIED in M1, M4, M8
├── config.py                       # NEW in M8
├── api/
│   ├── routes.py                   # DEPRECATED after M4
│   ├── blueprint.py                # NEW in M4
│   ├── pages/                      # NEW in M4
│   │   ├── __init__.py
│   │   ├── home.py                 # M4a
│   │   ├── check_cik.py            # M4b
│   │   ├── daily_values.py         # M4c
│   │   ├── admin.py                # M4d
│   │   └── db_check.py             # M4e
│   ├── api_v1/                     # NEW in M6
│   │   ├── __init__.py
│   │   ├── blueprint.py
│   │   └── admin.py
│   ├── jobs/                       # NEW in M3
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── services/                   # NEW in M5
│   │   ├── __init__.py
│   │   └── daily_values_service.py
│   └── schemas/                    # NEW in M6
│       ├── __init__.py
│       └── api_responses.py
├── templates/                      # NEW in M1
│   ├── base.html
│   ├── components/
│   │   ├── navbar.html
│   │   └── flash.html
│   ├── pages/
│   │   ├── home.html               # M9a
│   │   ├── check_cik.html          # M9b
│   │   ├── daily_values.html       # M9c
│   │   ├── admin.html              # M2
│   │   └── db_check.html           # M9d
│   └── errors/
│       ├── 404.html                # M8
│       └── 500.html                # M8
└── static/                         # NEW in M1
    ├── css/
    │   ├── app.css
    │   └── components.css
    └── js/
        ├── admin.js                # M2, M7 (enhanced)
        └── daily_values.js         # M9c
```

---

## 🚀 Implementation Milestones (Session-Optimized)

### 📌 Milestone 0: Baseline Documentation (10-15 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Low
**Risk**: None (no code changes)

**Goal**: Establish safety net before refactoring.

**Agent Instructions:**
1. Read `api/routes.py` completely (all 886 lines)
2. Create `docs/SMOKE_TEST.md` with smoke test checklist
3. Document all current routes by extracting them from routes.py
4. Run `pytest pytests/` to verify baseline tests pass
5. Manually test 2-3 critical routes

**Validation Checklist:**
- [ ] `docs/SMOKE_TEST.md` exists with complete checklist
- [ ] Route documentation created (list all @api_bp.route decorators)
- [ ] pytest runs successfully
- [ ] No code modified

**Deliverables:**
- `docs/SMOKE_TEST.md`
- `docs/CURRENT_ROUTES.md` (list of all routes with methods and handlers)

**Time Estimate**: 10-15 minutes

---

### 📌 Milestone 1: Template & Static Infrastructure (20-30 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Low
**Risk**: Low (only file creation, no logic changes)

**Goal**: Create folder structure and base templates WITHOUT changing routes.

**Agent Instructions:**

**Step 1: Create directories**
```bash
mkdir -p templates/pages templates/components templates/errors
mkdir -p static/css static/js
mkdir -p docs
```

**Step 2: Create `templates/base.html`**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}SEC Data{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}">
    {% block head %}{% endblock %}
</head>
<body>
    {% include 'components/navbar.html' %}
    
    <main class="container">
        {% block content %}{% endblock %}
    </main>
    
    <footer>
        <p>&copy; 2026 SEC Data</p>
    </footer>
    
    {% block scripts %}{% endblock %}
</body>
</html>
```

**Step 3: Create `templates/components/navbar.html`**
```html
<nav class="navbar">
    <div class="nav-container">
        <a href="/" class="nav-brand">SEC Data</a>
        <ul class="nav-links">
            <li><a href="/">Home</a></li>
            <li><a href="/check-cik">Check CIK</a></li>
            <li><a href="/daily-values">Daily Values</a></li>
            <li><a href="/admin">Admin</a></li>
            <li><a href="/db-check">DB Check</a></li>
        </ul>
    </div>
</nav>
```

**Step 4: Create `templates/components/flash.html`**
```html
{% if message %}
<div class="flash {{ message_type }}">
    {{ message }}
</div>
{% endif %}
```

**Step 5: Create `static/css/app.css`** (extract common patterns from routes.py)
```css
/* Global Styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    line-height: 1.6;
    color: #333;
    background-color: #f5f5f5;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

/* Navigation */
.navbar {
    background-color: #2c3e50;
    color: white;
    padding: 1rem 0;
}

.nav-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.nav-brand {
    color: white;
    text-decoration: none;
    font-size: 1.5rem;
    font-weight: bold;
}

.nav-links {
    display: flex;
    list-style: none;
    gap: 2rem;
}

.nav-links a {
    color: white;
    text-decoration: none;
}

.nav-links a:hover {
    text-decoration: underline;
}

/* Forms */
form {
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    margin-bottom: 20px;
}

input[type="text"],
input[type="number"],
select,
textarea {
    width: 100%;
    padding: 10px;
    margin: 8px 0;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 14px;
}

button,
input[type="submit"] {
    background-color: #3498db;
    color: white;
    padding: 10px 20px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    margin: 5px;
}

button:hover,
input[type="submit"]:hover {
    background-color: #2980b9;
}

button.danger {
    background-color: #e74c3c;
}

button.danger:hover {
    background-color: #c0392b;
}

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    background: white;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    margin: 20px 0;
}

th, td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #ddd;
}

th {
    background-color: #34495e;
    color: white;
    font-weight: bold;
}

tr:hover {
    background-color: #f5f5f5;
}

/* Status messages */
.flash {
    padding: 15px;
    margin: 20px 0;
    border-radius: 4px;
}

.flash.success {
    background-color: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
}

.flash.error {
    background-color: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
}

.flash.warning {
    background-color: #fff3cd;
    color: #856404;
    border: 1px solid #ffeaa7;
}

/* Card layout */
.card {
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    margin-bottom: 20px;
}

.card h2 {
    margin-bottom: 15px;
    color: #2c3e50;
}

/* Footer */
footer {
    text-align: center;
    padding: 20px;
    color: #7f8c8d;
    margin-top: 40px;
}
```

**Step 6: Create `static/css/components.css`**
```css
/* Job status components */
.job-status {
    display: grid;
    gap: 20px;
    margin: 20px 0;
}

.status-card {
    background: white;
    padding: 20px;
    border-radius: 8px;
    border-left: 4px solid #3498db;
}

.status-card.running {
    border-left-color: #2ecc71;
}

.status-card.error {
    border-left-color: #e74c3c;
}

.status-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #ecf0f1;
}

.status-row:last-child {
    border-bottom: none;
}

.status-label {
    font-weight: bold;
    color: #7f8c8d;
}

.status-value {
    color: #2c3e50;
}

/* Filter section */
.filters {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
    margin-bottom: 20px;
}

.filter-group {
    display: flex;
    flex-direction: column;
}

.filter-group label {
    font-weight: bold;
    margin-bottom: 5px;
    color: #2c3e50;
}
```

**Step 7: Create placeholder templates**
```bash
# Create empty placeholders
touch templates/pages/home.html
touch templates/pages/check_cik.html
touch templates/pages/daily_values.html
touch templates/pages/admin.html
touch templates/pages/db_check.html
```

Each placeholder should contain:
```jinja2
{% extends 'base.html' %}

{% block title %}Page Name - SEC Data{% endblock %}

{% block content %}
<h1>Page Name</h1>
<p>Placeholder - to be filled in later milestones</p>
{% endblock %}
```

**Step 8: Create empty JS files**
```javascript
// static/js/admin.js
console.log('Admin JS loaded');

// static/js/daily_values.js
console.log('Daily values JS loaded');
```

**Step 9: Test static file serving**
Start the app and verify:
- `http://localhost:5000/static/css/app.css` returns CSS
- `http://localhost:5000/static/js/admin.js` returns JS

**Validation Checklist:**
- [ ] All directories created
- [ ] `templates/base.html` exists with proper structure
- [ ] `templates/components/navbar.html` exists
- [ ] `static/css/app.css` has styles
- [ ] `static/css/components.css` has component styles
- [ ] All placeholder templates exist and extend base.html
- [ ] Empty JS files created
- [ ] Static files are accessible via browser
- [ ] All smoke tests still pass (routes unchanged)
- [ ] No Python errors when starting app

**Time Estimate**: 20-30 minutes

---

### 📌 Milestone 2: Migrate `/admin` to Templates (30-40 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Medium
**Risk**: Medium (first template migration, but well-scoped)

**Goal**: Convert `/admin` route from inline HTML to template files.

**Agent Instructions:**

**Step 1: Read and understand `/admin` route**
- Read the `/admin` GET route handler in `api/routes.py`
- Identify all template variables being passed
- Note the inline HTML structure
- Find all `<style>` and `<script>` blocks

**Step 2: Extract HTML to `templates/pages/admin.html`**
```jinja2
{% extends 'base.html' %}

{% block title %}Admin - SEC Data{% endblock %}

{% block content %}
<h1>Admin Dashboard</h1>

<!-- Populate Daily Values Job -->
<div class="card">
    <h2>Populate Daily Values Job</h2>
    
    <div class="status-card {% if populate_running %}running{% endif %}">
        <div class="status-row">
            <span class="status-label">Status:</span>
            <span class="status-value">{{ 'Running' if populate_running else 'Not Running' }}</span>
        </div>
        <div class="status-row">
            <span class="status-label">Started:</span>
            <span class="status-value">{{ populate_started_at or 'N/A' }}</span>
        </div>
        <div class="status-row">
            <span class="status-label">Ended:</span>
            <span class="status-value">{{ populate_ended_at or 'N/A' }}</span>
        </div>
        <div class="status-row">
            <span class="status-label">Last Log Line:</span>
            <span class="status-value last-log-line">{{ populate_last_log or 'N/A' }}</span>
        </div>
        {% if populate_error %}
        <div class="status-row">
            <span class="status-label">Error:</span>
            <span class="status-value error">{{ populate_error }}</span>
        </div>
        {% endif %}
    </div>
    
    <form method="POST" action="/admin/populate-daily-values">
        <input type="hidden" name="confirm" value="{{ populate_confirm_token }}">
        <button type="submit">Start Populate Job</button>
    </form>
    
    <form method="POST" action="/admin/stop-populate">
        <input type="hidden" name="confirm" value="{{ stop_confirm_token }}">
        <button type="submit" class="danger">Stop Populate Job</button>
    </form>
</div>

<!-- Recreate DB Job -->
<div class="card">
    <h2>Recreate Database Job</h2>
    
    <div class="status-card {% if recreate_running %}running{% endif %}">
        <div class="status-row">
            <span class="status-label">Status:</span>
            <span class="status-value">{{ 'Running' if recreate_running else 'Not Running' }}</span>
        </div>
        <div class="status-row">
            <span class="status-label">Started:</span>
            <span class="status-value">{{ recreate_started_at or 'N/A' }}</span>
        </div>
        <div class="status-row">
            <span class="status-label">Ended:</span>
            <span class="status-value">{{ recreate_ended_at or 'N/A' }}</span>
        </div>
        {% if recreate_error %}
        <div class="status-row">
            <span class="status-label">Error:</span>
            <span class="status-value error">{{ recreate_error }}</span>
        </div>
        {% endif %}
    </div>
    
    <form method="POST" action="/admin/recreate-db">
        <input type="hidden" name="confirm" value="{{ recreate_confirm_token }}">
        <button type="submit" class="danger">Recreate Database (Destructive!)</button>
    </form>
</div>

<!-- Init DB -->
<div class="card">
    <h2>Initialize Database Tables</h2>
    <form method="POST" action="/admin/init-db">
        <input type="hidden" name="confirm" value="{{ init_confirm_token }}">
        <button type="submit">Initialize DB Schema</button>
    </form>
</div>
{% endblock %}

{% block scripts %}
<script src="{{ url_for('static', filename='js/admin.js') }}"></script>
{% endblock %}
```

**Step 3: Update route handler in `api/routes.py`**
Find the `/admin` route and replace:
```python
@api_bp.route("/admin", methods=["GET"])
def admin():
    # ...existing logic to gather status...
    
    # OLD: return render_template_string(html_string, ...)
    # NEW:
    return render_template('pages/admin.html',
        populate_running=populate_running,
        populate_started_at=populate_started_at,
        populate_ended_at=populate_ended_at,
        populate_last_log=populate_last_log,
        populate_error=populate_error,
        populate_confirm_token=populate_confirm_token,
        stop_confirm_token=stop_confirm_token,
        recreate_running=recreate_running,
        recreate_started_at=recreate_started_at,
        recreate_ended_at=recreate_ended_at,
        recreate_error=recreate_error,
        recreate_confirm_token=recreate_confirm_token,
        init_confirm_token=init_confirm_token
    )
```

**Step 4: Test admin page**
- Start app: `python app.py`
- Visit `http://localhost:5000/admin`
- Verify page renders correctly
- Test starting populate job
- Test stopping populate job
- Test recreate DB button
- Verify confirmation tokens work

**Validation Checklist:**
- [ ] `/admin` uses `render_template()` not `render_template_string()`
- [ ] No inline CSS in admin.html
- [ ] No inline JavaScript in admin.html
- [ ] Admin page displays correctly
- [ ] All buttons work (start/stop jobs)
- [ ] Confirmation tokens validated
- [ ] Job status updates display
- [ ] All smoke tests pass
- [ ] No Python errors
- [ ] No browser console errors

**Time Estimate**: 30-40 minutes

---

### 📌 Milestone 3: Extract Background Job Manager (25-35 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Medium
**Risk**: Medium (thread safety critical)

**Goal**: Move job management code out of routes.py into dedicated module.

**Agent Instructions:**

**Step 1: Create `api/jobs/__init__.py`**
```python
"""Background job management for admin tasks."""
```

**Step 2: Create `api/jobs/manager.py`**
```python
import os
import threading
import time
import traceback


def read_last_log_line(log_path: str, max_bytes: int = 64 * 1024) -> str:
    """Return last non-empty line from a log file (best-effort)."""
    try:
        if not os.path.exists(log_path):
            return "(log file not found)"
        with open(log_path, "rb") as f:
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - max_bytes), os.SEEK_SET)
            except Exception:
                f.seek(0)
            data = f.read().decode("utf-8", errors="replace")
        lines = [ln.strip() for ln in data.splitlines() if ln.strip()]
        return lines[-1] if lines else "(log is empty)"
    except Exception as e:
        return f"(failed to read log: {e})"


class PopulateJobManager:
    """Manages the populate_daily_values background job."""
    
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {
            "running": False,
            "started_at": None,
            "ended_at": None,
            "error": None,
            "stop_requested": False,
        }
        self.log_path = "populate_daily_values.log"
    
    def start(self) -> bool:
        """Start the populate job. Returns True if started, False if already running."""
        with self.lock:
            if self.state["running"]:
                return False
            self.state.update({
                "running": True,
                "started_at": time.time(),
                "ended_at": None,
                "error": None,
                "stop_requested": False,
            })
        
        def runner():
            try:
                # Ensure schema exists
                from db import Base, engine
                Base.metadata.create_all(bind=engine)
                
                # Check if stop requested before starting
                with self.lock:
                    if self.state.get("stop_requested"):
                        return
                
                # Run the populate job
                from utils import populate_daily_values
                populate_daily_values.main()
            except Exception:
                with self.lock:
                    self.state["error"] = traceback.format_exc()
            finally:
                with self.lock:
                    self.state["running"] = False
                    self.state["ended_at"] = time.time()
        
        thread = threading.Thread(target=runner, name="populate_daily_values", daemon=True)
        thread.start()
        return True
    
    def request_stop(self):
        """Request cooperative stop of the job."""
        with self.lock:
            self.state["stop_requested"] = True
    
    def get_status(self) -> dict:
        """Get current job status."""
        with self.lock:
            status = self.state.copy()
        
        # Add last log line
        status["last_log_line"] = read_last_log_line(self.log_path)
        
        # Format timestamps
        if status["started_at"]:
            status["started_at_formatted"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(status["started_at"])
            )
        if status["ended_at"]:
            status["ended_at_formatted"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(status["ended_at"])
            )
        
        return status


class RecreateJobManager:
    """Manages the recreate_sqlite_db background job."""
    
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {
            "running": False,
            "started_at": None,
            "ended_at": None,
            "error": None,
        }
    
    def start(self) -> bool:
        """Start the recreate DB job. Returns True if started, False if already running."""
        with self.lock:
            if self.state["running"]:
                return False
            self.state.update({
                "running": True,
                "started_at": time.time(),
                "ended_at": None,
                "error": None,
            })
        
        def runner():
            try:
                from utils import recreate_sqlite_db
                recreate_sqlite_db.main()
            except Exception:
                with self.lock:
                    self.state["error"] = traceback.format_exc()
            finally:
                with self.lock:
                    self.state["running"] = False
                    self.state["ended_at"] = time.time()
        
        thread = threading.Thread(target=runner, name="recreate_sqlite_db", daemon=True)
        thread.start()
        return True
    
    def get_status(self) -> dict:
        """Get current job status."""
        with self.lock:
            status = self.state.copy()
        
        # Format timestamps
        if status["started_at"]:
            status["started_at_formatted"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(status["started_at"])
            )
        if status["ended_at"]:
            status["ended_at_formatted"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(status["ended_at"])
            )
        
        return status


# Singleton instances
populate_job_manager = PopulateJobManager()
recreate_job_manager = RecreateJobManager()
```

**Step 3: Update `api/routes.py` to use managers**
Replace all direct job state access with manager calls:

```python
# At top of file, add import:
from api.jobs.manager import populate_job_manager, recreate_job_manager

# In /admin route, replace state access:
@api_bp.route("/admin", methods=["GET"])
def admin():
    populate_status = populate_job_manager.get_status()
    recreate_status = recreate_job_manager.get_status()
    
    # Generate confirmation tokens
    import secrets
    populate_confirm_token = secrets.token_hex(16)
    # ... etc
    
    return render_template('pages/admin.html',
        populate_running=populate_status["running"],
        populate_started_at=populate_status.get("started_at_formatted"),
        populate_ended_at=populate_status.get("ended_at_formatted"),
        populate_last_log=populate_status.get("last_log_line"),
        populate_error=populate_status.get("error"),
        # ... etc
    )

# In populate job start route:
@api_bp.route("/admin/populate-daily-values", methods=["POST"])
def admin_populate_daily_values_post():
    # ... confirmation token validation ...
    
    started = populate_job_manager.start()
    if started:
        return jsonify({"ok": True, "message": "Job started"})
    else:
        return jsonify({"ok": False, "message": "Job already running"}), 409

# In stop route:
@api_bp.route("/admin/stop-populate", methods=["POST"])
def admin_stop_populate():
    # ... confirmation validation ...
    
    populate_job_manager.request_stop()
    return jsonify({"ok": True, "message": "Stop requested"})

# Similar for recreate DB routes...
```

**Step 4: Remove old job management code**
Delete or comment out:
- `_populate_job_lock`, `_populate_job_state`
- `_recreate_job_lock`, `_recreate_job_state`
- `_start_populate_daily_values_background()`
- `_start_recreate_sqlite_db_background()`
- `_read_last_log_line()`

**Step 5: Test job management**
- Start app
- Visit `/admin`
- Start populate job - verify it starts
- Check status updates
- Stop job - verify stop request
- Start recreate job - verify it works

**Validation Checklist:**
- [ ] `api/jobs/manager.py` created with both manager classes
- [ ] `api/routes.py` imports and uses managers
- [ ] Old job management code removed from routes.py
- [ ] All admin job operations work (start/stop/status)
- [ ] Thread safety preserved (locks work correctly)
- [ ] All smoke tests pass
- [ ] No race conditions or deadlocks

**Time Estimate**: 25-35 minutes

---

### 📌 Milestone 4a: Split Routes - Home & Check CIK (30-40 min)

**Session Scope**: ✅ FITS IN ONE SESSION (split M4 into sub-milestones)
**Complexity**: Medium
**Risk**: Medium (first blueprint split)

**Goal**: Create blueprint structure and migrate home + check_cik routes.

**Agent Instructions:**

**Step 1: Create `api/pages/__init__.py`**
```python
"""Page route blueprints for HTML responses."""
```

**Step 2: Create `api/pages/home.py`**
```python
from flask import Blueprint, render_template_string

bp = Blueprint('home', __name__)

@bp.route('/')
def index():
    # Copy the existing route handler logic from api/routes.py
    # Keep render_template_string for now (will migrate in M9)
    pass
```

**Step 3: Create `api/pages/check_cik.py`**
```python
from flask import Blueprint, render_template_string, request, redirect, url_for
from db import SessionLocal
from models.entities import Entity

bp = Blueprint('check_cik', __name__)

@bp.route('/check-cik', methods=['GET', 'POST'])
def check_cik():
    # Copy the existing route handler logic from api/routes.py
    # Keep render_template_string for now (will migrate in M9)
    pass
```

**Step 4: Create `api/blueprint.py`**
```python
from flask import Blueprint

def create_api_blueprint():
    """Create and configure the main API blueprint."""
    api_bp = Blueprint("api", __name__)
    
    # Register page blueprints
    from .pages import home, check_cik
    
    api_bp.register_blueprint(home.bp)
    api_bp.register_blueprint(check_cik.bp)
    
    return api_bp
```

**Step 5: Update `app.py`**
```python
from flask import Flask
from api.blueprint import create_api_blueprint
import os

from db import engine, Base

def init_db() -> None:
    """Initialize DB schema."""
    Base.metadata.create_all(bind=engine)

app = Flask(__name__)

# Register blueprint
api_bp = create_api_blueprint()
app.register_blueprint(api_bp)

# Optional: initialize tables on startup
if os.getenv("INIT_DB_ON_STARTUP", "0") == "1":
    init_db()

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
```

**Step 6: Update `api/routes.py`**
Comment out the migrated routes but keep the file for reference.

**Step 7: Test thoroughly**
- Test `/` - home page
- Test `/check-cik` GET - form displays
- Test `/check-cik` POST - redirects work

**Validation Checklist:**
- [ ] `api/blueprint.py` exists and creates main blueprint
- [ ] `api/pages/home.py` handles `/`
- [ ] `api/pages/check_cik.py` handles `/check-cik`
- [ ] `app.py` uses new blueprint structure
- [ ] Home page loads
- [ ] Check CIK form works
- [ ] Check CIK redirect works
- [ ] All smoke tests pass
- [ ] No import errors

**Time Estimate**: 30-40 minutes

---

### 📌 Milestone 4b: Split Routes - Daily Values (25-35 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Medium
**Risk**: Medium (complex route with query logic)

**Goal**: Migrate `/daily-values` route to separate module.

**Agent Instructions:**

**Step 1: Create `api/pages/daily_values.py`**
```python
from flask import Blueprint, render_template_string, request
from db import SessionLocal
from models.daily_values import DailyValue
from models.entities import Entity
from models.value_names import ValueName
from models.units import Unit
from sqlalchemy import distinct

bp = Blueprint('daily_values', __name__)

@bp.route('/daily-values', methods=['GET'])
def daily_values():
    # Copy the entire /daily-values route handler from api/routes.py
    # Include all query building logic
    # Keep render_template_string for now (will migrate in M9)
    pass
```

**Step 2: Update `api/blueprint.py`**
```python
def create_api_blueprint():
    api_bp = Blueprint("api", __name__)
    
    from .pages import home, check_cik, daily_values
    
    api_bp.register_blueprint(home.bp)
    api_bp.register_blueprint(check_cik.bp)
    api_bp.register_blueprint(daily_values.bp)  # NEW
    
    return api_bp
```

**Step 3: Comment out `/daily-values` in `api/routes.py`**

**Step 4: Test daily values page**
- Visit `/daily-values`
- Test filters (entity_id, value_names, unit)
- Verify query parameters preserved
- Check pagination/limits

**Validation Checklist:**
- [ ] `api/pages/daily_values.py` created
- [ ] Registered in blueprint
- [ ] `/daily-values` page loads
- [ ] All filters work
- [ ] Query parameters preserved
- [ ] Data displays correctly
- [ ] All smoke tests pass

**Time Estimate**: 25-35 minutes

---

### 📌 Milestone 4c: Split Routes - Admin & DB Check (30-40 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Medium
**Risk**: Medium (multiple routes per file)

**Goal**: Migrate admin and db-check routes to separate modules.

**Agent Instructions:**

**Step 1: Create `api/pages/admin.py`**
```python
from flask import Blueprint, render_template, request, jsonify
from api.jobs.manager import populate_job_manager, recreate_job_manager
import secrets

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('', methods=['GET'])
def admin():
    # Copy /admin route logic
    pass

@bp.route('/populate-daily-values', methods=['GET', 'POST'])
def populate_daily_values():
    # Copy both GET and POST logic
    pass

@bp.route('/stop-populate', methods=['POST'])
def stop_populate():
    # Copy logic
    pass

@bp.route('/recreate-db', methods=['GET', 'POST'])
def recreate_db():
    # Copy logic
    pass

@bp.route('/init-db', methods=['POST'])
def init_db():
    # Copy logic
    pass
```

**Step 2: Create `api/pages/db_check.py`**
```python
from flask import Blueprint, render_template_string, request
from db import SessionLocal, engine
from sqlalchemy import inspect, text

bp = Blueprint('db_check', __name__)

@bp.route('/db-check', methods=['GET'])
def db_check():
    # Copy route logic
    pass

@bp.route('/sql', methods=['POST'])
def execute_sql():
    # Copy route logic
    pass
```

**Step 3: Update `api/blueprint.py`**
```python
def create_api_blueprint():
    api_bp = Blueprint("api", __name__)
    
    from .pages import home, check_cik, daily_values, admin, db_check
    
    api_bp.register_blueprint(home.bp)
    api_bp.register_blueprint(check_cik.bp)
    api_bp.register_blueprint(daily_values.bp)
    api_bp.register_blueprint(admin.bp)  # NEW
    api_bp.register_blueprint(db_check.bp)  # NEW
    
    return api_bp
```

**Step 4: Test all admin and db-check routes**

**Validation Checklist:**
- [ ] `api/pages/admin.py` created with all admin routes
- [ ] `api/pages/db_check.py` created
- [ ] All routes registered
- [ ] `/admin` works
- [ ] All admin actions work (start/stop/recreate)
- [ ] `/db-check` page loads
- [ ] SQL query execution works
- [ ] All smoke tests pass
- [ ] `api/routes.py` can be deleted or archived

**Time Estimate**: 30-40 minutes

---

### 📌 Milestone 5: Create Services Layer (25-35 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Medium
**Risk**: Low (pure extraction, no behavior change)

**Goal**: Extract query building logic from routes to service layer.

**Agent Instructions:**

**Step 1: Create `api/services/__init__.py`**
```python
"""Service layer for business logic."""
```

**Step 2: Create `api/services/daily_values_service.py`**
```python
from typing import List, Optional
from sqlalchemy.orm import Session
from models.daily_values import DailyValue
from models.entities import Entity
from models.value_names import ValueName
from models.units import Unit


def build_daily_values_query(
    session: Session,
    entity_id: Optional[int] = None,
    value_name_ids: Optional[List[int]] = None,
    unit: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
):
    """Build filtered query for daily values.
    
    Args:
        session: Database session
        entity_id: Filter by entity ID
        value_name_ids: Filter by value name IDs
        unit: Filter by unit
        start_date: Filter by start date (YYYY-MM-DD)
        end_date: Filter by end date (YYYY-MM-DD)
        limit: Maximum number of results
        
    Returns:
        SQLAlchemy query object
    """
    query = session.query(DailyValue)
    
    if entity_id:
        query = query.filter(DailyValue.entity_id == entity_id)
    
    if value_name_ids:
        query = query.filter(DailyValue.value_name_id.in_(value_name_ids))
    
    if unit:
        query = query.filter(DailyValue.unit == unit)
    
    if start_date:
        query = query.filter(DailyValue.date_id >= start_date)
    
    if end_date:
        query = query.filter(DailyValue.date_id <= end_date)
    
    query = query.order_by(DailyValue.date_id.desc())
    
    return query.limit(limit)


def get_filter_options(session: Session) -> dict:
    """Get distinct values for filter dropdowns.
    
    Returns:
        Dict with entities, value_names, and units for filters
    """
    entities = session.query(Entity).order_by(Entity.name).all()
    value_names = session.query(ValueName).order_by(ValueName.name).all()
    units = session.query(Unit).order_by(Unit.unit).all()
    
    return {
        'entities': entities,
        'value_names': value_names,
        'units': units
    }


def get_entity_by_cik(session: Session, cik: str) -> Optional[Entity]:
    """Look up entity by CIK code.
    
    Args:
        session: Database session
        cik: CIK code (will be zero-padded to 10 digits)
        
    Returns:
        Entity object or None if not found
    """
    # Zero-pad CIK to 10 digits
    cik_padded = cik.zfill(10)
    return session.query(Entity).filter(Entity.cik == cik_padded).first()
```

**Step 3: Update `api/pages/daily_values.py` to use service**
```python
from api.services.daily_values_service import build_daily_values_query, get_filter_options

@bp.route('/daily-values', methods=['GET'])
def daily_values():
    session = SessionLocal()
    try:
        # Extract filter parameters from request
        entity_id = request.args.get('entity_id', type=int)
        value_name_ids = request.args.getlist('value_names[]', type=int)
        unit = request.args.get('unit')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 100, type=int)
        
        # Use service to build query
        query = build_daily_values_query(
            session,
            entity_id=entity_id,
            value_name_ids=value_name_ids if value_name_ids else None,
            unit=unit,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        results = query.all()
        
        # Get filter options
        filter_options = get_filter_options(session)
        
        # Render template with results
        return render_template_string(html_template,
            results=results,
            **filter_options
        )
    finally:
        session.close()
```

**Step 4: Update `api/pages/check_cik.py` to use service**
```python
from api.services.daily_values_service import get_entity_by_cik

@bp.route('/check-cik', methods=['POST'])
def check_cik_post():
    cik = request.form.get('cik', '').strip()
    
    session = SessionLocal()
    try:
        entity = get_entity_by_cik(session, cik)
        
        if entity:
            return redirect(url_for('daily_values.daily_values', entity_id=entity.id))
        else:
            return render_template_string(html_template,
                error=f"No entity found for CIK: {cik}"
            )
    finally:
        session.close()
```

**Validation Checklist:**
- [ ] `api/services/daily_values_service.py` created
- [ ] Service functions are pure (no Flask dependencies)
- [ ] `api/pages/daily_values.py` uses service
- [ ] `api/pages/check_cik.py` uses service
- [ ] All daily values filters work
- [ ] CIK lookup works
- [ ] Service functions have docstrings
- [ ] All smoke tests pass

**Time Estimate**: 25-35 minutes

---

### 📌 Milestone 6: Create `/api/v1` JSON Endpoints (30-40 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Medium
**Risk**: Low (additive, doesn't change existing routes)

**Goal**: Create versioned JSON API with standard response format.

**Agent Instructions:**

**Step 1: Install Pydantic (if not already installed)**
```bash
pip install pydantic
```

**Step 2: Create `api/schemas/__init__.py`**
```python
"""Pydantic schemas for API request/response validation."""
```

**Step 3: Create `api/schemas/api_responses.py`**
```python
from typing import Optional, Any, Dict
from pydantic import BaseModel


class APIResponse(BaseModel):
    """Standard API response envelope."""
    ok: bool
    data: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "ok": True,
                "data": {"key": "value"},
                "error": None,
                "meta": {"version": "1.0"}
            }
        }


class ErrorDetail(BaseModel):
    """Error detail structure."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
```

**Step 4: Create `api/api_v1/__init__.py`**
```python
"""JSON API v1 endpoints."""
```

**Step 5: Create `api/api_v1/blueprint.py`**
```python
from flask import Blueprint


def create_api_v1_blueprint():
    """Create and configure API v1 blueprint."""
    api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')
    
    # Register v1 endpoint blueprints
    from . import admin
    api_v1_bp.register_blueprint(admin.bp)
    
    return api_v1_bp
```

**Step 6: Create `api/api_v1/admin.py`**
```python
from flask import Blueprint, jsonify
from api.jobs.manager import populate_job_manager, recreate_job_manager
from api.schemas.api_responses import APIResponse

bp = Blueprint('admin_api', __name__, url_prefix='/admin')


@bp.route('/jobs', methods=['GET'])
def get_jobs_status():
    """Get status of all background jobs.
    
    Returns:
        JSON response with job statuses
    """
    try:
        populate_status = populate_job_manager.get_status()
        recreate_status = recreate_job_manager.get_status()
        
        data = {
            'populate': {
                'running': populate_status['running'],
                'started_at': populate_status.get('started_at_formatted'),
                'ended_at': populate_status.get('ended_at_formatted'),
                'last_log_line': populate_status.get('last_log_line'),
                'error': populate_status.get('error'),
                'stop_requested': populate_status.get('stop_requested', False)
            },
            'recreate': {
                'running': recreate_status['running'],
                'started_at': recreate_status.get('started_at_formatted'),
                'ended_at': recreate_status.get('ended_at_formatted'),
                'error': recreate_status.get('error')
            }
        }
        
        response = APIResponse(ok=True, data=data)
        return jsonify(response.dict())
        
    except Exception as e:
        response = APIResponse(
            ok=False,
            error={
                'code': 'SERVER_ERROR',
                'message': str(e)
            }
        )
        return jsonify(response.dict()), 500
```

**Step 7: Update `api/blueprint.py` to register API v1**
```python
from .api_v1.blueprint import create_api_v1_blueprint

def create_api_blueprint():
    api_bp = Blueprint("api", __name__)
    
    # Register page blueprints
    from .pages import home, check_cik, daily_values, admin, db_check
    api_bp.register_blueprint(home.bp)
    api_bp.register_blueprint(check_cik.bp)
    api_bp.register_blueprint(daily_values.bp)
    api_bp.register_blueprint(admin.bp)
    api_bp.register_blueprint(db_check.bp)
    
    # Register API v1
    api_v1_bp = create_api_v1_blueprint()
    api_bp.register_blueprint(api_v1_bp)
    
    return api_bp
```

**Step 8: Test the new API endpoint**
```bash
# Start app
python app.py

# Test API endpoint
curl http://localhost:5000/api/v1/admin/jobs
```

Expected response:
```json
{
  "ok": true,
  "data": {
    "populate": {
      "running": false,
      "started_at": null,
      "ended_at": null,
      "last_log_line": "(log file not found)",
      "error": null,
      "stop_requested": false
    },
    "recreate": {
      "running": false,
      "started_at": null,
      "ended_at": null,
      "error": null
    }
  },
  "error": null,
  "meta": null
}
```

**Validation Checklist:**
- [ ] Pydantic installed
- [ ] `api/schemas/api_responses.py` created
- [ ] `api/api_v1/admin.py` created
- [ ] `/api/v1/admin/jobs` endpoint works
- [ ] Response follows standard envelope format
- [ ] Pydantic validates responses
- [ ] Error responses use same format
- [ ] All smoke tests still pass (HTML routes unchanged)
- [ ] No errors in console

**Time Estimate**: 30-40 minutes

---

### 📌 Milestone 7: Enhance Admin with Live Updates (OPTIONAL) (20-30 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Low
**Risk**: Low (JavaScript enhancement only)

**Goal**: Add polling to admin page for real-time status updates.

**Agent Instructions:**

**Step 1: Update `static/js/admin.js`**
```javascript
// Admin page JavaScript enhancements

// Poll job status every 5 seconds
const POLL_INTERVAL = 5000;
let pollTimer = null;

async function updateJobStatus() {
    try {
        const response = await fetch('/api/v1/admin/jobs');
        if (!response.ok) {
            console.error('Failed to fetch job status:', response.statusText);
            return;
        }
        
        const result = await response.json();
        
        if (result.ok && result.data) {
            // Update populate job status
            updatePopulateStatus(result.data.populate);
            
            // Update recreate job status
            updateRecreateStatus(result.data.recreate);
            
            // Update last refreshed time
            updateLastRefreshed();
        }
    } catch (error) {
        console.error('Failed to fetch job status:', error);
    }
}

function updatePopulateStatus(jobData) {
    // Update running status
    const runningEl = document.querySelector('#populate-status .status-running');
    if (runningEl) {
        runningEl.textContent = jobData.running ? 'Running' : 'Not Running';
        runningEl.classList.toggle('running', jobData.running);
    }
    
    // Update last log line
    const logEl = document.querySelector('#populate-status .last-log-line');
    if (logEl && jobData.last_log_line) {
        logEl.textContent = jobData.last_log_line;
    }
    
    // Update timestamps
    const startedEl = document.querySelector('#populate-status .started-at');
    if (startedEl) {
        startedEl.textContent = jobData.started_at || 'N/A';
    }
    
    const endedEl = document.querySelector('#populate-status .ended-at');
    if (endedEl) {
        endedEl.textContent = jobData.ended_at || 'N/A';
    }
    
    // Update error (if any)
    const errorEl = document.querySelector('#populate-status .error');
    if (errorEl) {
        if (jobData.error) {
            errorEl.textContent = jobData.error;
            errorEl.style.display = 'block';
        } else {
            errorEl.style.display = 'none';
        }
    }
}

function updateRecreateStatus(jobData) {
    const runningEl = document.querySelector('#recreate-status .status-running');
    if (runningEl) {
        runningEl.textContent = jobData.running ? 'Running' : 'Not Running';
        runningEl.classList.toggle('running', jobData.running);
    }
    
    const startedEl = document.querySelector('#recreate-status .started-at');
    if (startedEl) {
        startedEl.textContent = jobData.started_at || 'N/A';
    }
    
    const endedEl = document.querySelector('#recreate-status .ended-at');
    if (endedEl) {
        endedEl.textContent = jobData.ended_at || 'N/A';
    }
    
    const errorEl = document.querySelector('#recreate-status .error');
    if (errorEl) {
        if (jobData.error) {
            errorEl.textContent = jobData.error;
            errorEl.style.display = 'block';
        } else {
            errorEl.style.display = 'none';
        }
    }
}

function updateLastRefreshed() {
    const refreshEl = document.getElementById('last-refreshed');
    if (refreshEl) {
        const now = new Date();
        refreshEl.textContent = `Last updated: ${now.toLocaleTimeString()}`;
    }
}

function startPolling() {
    // Initial update
    updateJobStatus();
    
    // Poll every 5 seconds
    pollTimer = setInterval(updateJobStatus, POLL_INTERVAL);
}

function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

// Start polling when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('Admin page loaded - starting status polling');
    startPolling();
});

// Stop polling when page unloads
window.addEventListener('beforeunload', () => {
    stopPolling();
});
```

**Step 2: Update `templates/pages/admin.html`**
Add IDs and classes for JavaScript to target:
```jinja2
<!-- Add last refreshed indicator -->
<div id="last-refreshed" style="text-align: right; color: #7f8c8d; font-size: 0.9em; margin: 10px 0;">
    Last updated: Never
</div>

<!-- Update populate status card -->
<div id="populate-status" class="status-card {% if populate_running %}running{% endif %}">
    <div class="status-row">
        <span class="status-label">Status:</span>
        <span class="status-value status-running">{{ 'Running' if populate_running else 'Not Running' }}</span>
    </div>
    <div class="status-row">
        <span class="status-label">Started:</span>
        <span class="status-value started-at">{{ populate_started_at or 'N/A' }}</span>
    </div>
    <div class="status-row">
        <span class="status-label">Ended:</span>
        <span class="status-value ended-at">{{ populate_ended_at or 'N/A' }}</span>
    </div>
    <div class="status-row">
        <span class="status-label">Last Log Line:</span>
        <span class="status-value last-log-line">{{ populate_last_log or 'N/A' }}</span>
    </div>
    {% if populate_error %}
    <div class="status-row">
        <span class="status-label">Error:</span>
        <span class="status-value error" style="color: red;">{{ populate_error }}</span>
    </div>
    {% endif %}
</div>

<!-- Similar for recreate status... -->
```

**Step 3: Add CSS for running indicator**
In `static/css/components.css`:
```css
.status-running {
    font-weight: bold;
}

.status-running.running {
    color: #2ecc71;
}

#last-refreshed {
    text-align: right;
    color: #7f8c8d;
    font-size: 0.9em;
    margin: 10px 0;
}
```

**Step 4: Test live updates**
- Start app
- Visit `/admin`
- Start a populate job
- Watch status update automatically without refresh
- Verify "Last updated" timestamp changes
- Check browser console for errors

**Validation Checklist:**
- [ ] `static/js/admin.js` has polling logic
- [ ] Admin page updates every 5 seconds
- [ ] Status changes reflect in real-time
- [ ] Last updated time displays
- [ ] Page still works with JavaScript disabled
- [ ] No console errors
- [ ] Polling stops when leaving page
- [ ] All smoke tests pass

**Time Estimate**: 20-30 minutes

---

### 📌 Milestone 8: Security Hardening (25-35 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Medium
**Risk**: Low (config-based, non-breaking)

**Goal**: Add configuration-based security controls.

**Agent Instructions:**

**Step 1: Create `config.py`**
```python
import os


class Config:
    """Application configuration."""
    
    # Debug mode
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Feature flags
    ENABLE_ADMIN = os.getenv('ENABLE_ADMIN', 'True').lower() == 'true'
    ENABLE_DB_CHECK = os.getenv('ENABLE_DB_CHECK', 'False').lower() == 'true'
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/sec.db')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
```

**Step 2: Update `app.py` to use config**
```python
from flask import Flask
from api.blueprint import create_api_blueprint
from config import Config
import os
import logging

from db import engine, Base


def init_db() -> None:
    """Initialize DB schema."""
    Base.metadata.create_all(bind=engine)


def create_app():
    """Application factory."""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(Config)
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, app.config['LOG_LEVEL']),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Register blueprints
    api_bp = create_api_blueprint()
    app.register_blueprint(api_bp)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return f"<h1>404 Not Found</h1><p>{e}</p>", 404
    
    @app.errorhandler(500)
    def server_error(e):
        app.logger.error(f'Server Error: {e}')
        return "<h1>500 Internal Server Error</h1><p>An error occurred. Please try again later.</p>", 500
    
    # Request logging
    @app.before_request
    def log_request():
        from flask import request
        app.logger.info(f'{request.method} {request.path}')
    
    # Optional: initialize tables on startup
    if os.getenv("INIT_DB_ON_STARTUP", "0") == "1":
        init_db()
    
    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=app.config['DEBUG'], use_reloader=False)
```

**Step 3: Update `api/blueprint.py` for conditional registration**
```python
from flask import Blueprint, current_app


def create_api_blueprint():
    """Create and configure the main API blueprint."""
    api_bp = Blueprint("api", __name__)
    
    # Always register core pages
    from .pages import home, check_cik, daily_values
    api_bp.register_blueprint(home.bp)
    api_bp.register_blueprint(check_cik.bp)
    api_bp.register_blueprint(daily_values.bp)
    
    # Conditionally register admin (disabled in production by default)
    # Note: current_app is available after app context is created
    # We'll use a lazy registration pattern
    @api_bp.record_once
    def register_conditional_blueprints(state):
        app = state.app
        
        if app.config.get('ENABLE_ADMIN', True):
            from .pages import admin
            api_bp.register_blueprint(admin.bp)
            app.logger.info('Admin routes enabled')
        else:
            app.logger.warning('Admin routes disabled')
        
        if app.config.get('ENABLE_DB_CHECK', False):
            from .pages import db_check
            api_bp.register_blueprint(db_check.bp)
            app.logger.info('DB check routes enabled')
        else:
            app.logger.info('DB check routes disabled (enable with ENABLE_DB_CHECK=true)')
    
    # Register API v1
    from .api_v1.blueprint import create_api_v1_blueprint
    api_v1_bp = create_api_v1_blueprint()
    api_bp.register_blueprint(api_v1_bp)
    
    return api_bp
```

**Step 4: Create error templates**
Create `templates/errors/404.html`:
```html
{% extends 'base.html' %}

{% block title %}404 Not Found{% endblock %}

{% block content %}
<div class="error-page">
    <h1>404 - Page Not Found</h1>
    <p>The page you're looking for doesn't exist.</p>
    <p><a href="/">Go to Home Page</a></p>
</div>
{% endblock %}
```

Create `templates/errors/500.html`:
```html
{% extends 'base.html' %}

{% block title %}500 Server Error{% endblock %}

{% block content %}
<div class="error-page">
    <h1>500 - Internal Server Error</h1>
    <p>Something went wrong on our end. Please try again later.</p>
    <p><a href="/">Go to Home Page</a></p>
</div>
{% endblock %}
```

**Step 5: Update error handlers to use templates**
```python
@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(e):
    app.logger.error(f'Server Error: {e}')
    return render_template('errors/500.html'), 500
```

**Step 6: Create `.env.example` file**
```bash
# Flask Configuration
FLASK_DEBUG=False
SECRET_KEY=your-secret-key-here

# Feature Flags
ENABLE_ADMIN=True
ENABLE_DB_CHECK=False

# Database
DATABASE_PATH=data/sec.db
INIT_DB_ON_STARTUP=0

# Logging
LOG_LEVEL=INFO
```

**Step 7: Test configuration**
```bash
# Test with admin disabled
ENABLE_ADMIN=False python app.py
# Try to access /admin - should get 404

# Test with admin enabled (default)
python app.py
# Admin should work

# Test with DB check enabled
ENABLE_DB_CHECK=True python app.py
# /db-check should work
```

**Validation Checklist:**
- [ ] `config.py` created
- [ ] `app.py` uses config
- [ ] Error templates created (404, 500)
- [ ] Conditional blueprint registration works
- [ ] `/admin` can be disabled via env var
- [ ] `/db-check` disabled by default
- [ ] Error pages render correctly
- [ ] Request logging works
- [ ] `.env.example` created
- [ ] All smoke tests pass (with admin enabled)

**Time Estimate**: 25-35 minutes

---

### 📌 Milestone 9a: Migrate Home to Template (15-20 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Low
**Risk**: Low

**Goal**: Migrate home page from inline HTML to template.

**Agent Instructions:**

**Step 1: Read current home route**
Find the inline HTML in `api/pages/home.py`

**Step 2: Create `templates/pages/home.html`**
Extract HTML and convert to Jinja2 template

**Step 3: Update `api/pages/home.py`**
```python
from flask import Blueprint, render_template

bp = Blueprint('home', __name__)

@bp.route('/')
def index():
    return render_template('pages/home.html')
```

**Step 4: Test**
- Visit `/`
- Verify page renders
- Check links work

**Validation Checklist:**
- [ ] `templates/pages/home.html` created
- [ ] No `render_template_string` in home.py
- [ ] Home page loads correctly
- [ ] All smoke tests pass

**Time Estimate**: 15-20 minutes

---

### 📌 Milestone 9b: Migrate Check CIK to Template (20-25 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Low
**Risk**: Low

**Goal**: Migrate check-cik page to template.

**Agent Instructions:**

**Step 1: Create `templates/pages/check_cik.html`**
**Step 2: Update `api/pages/check_cik.py`**
**Step 3: Test form submission and redirect**

**Validation Checklist:**
- [ ] Template created
- [ ] No inline HTML in route
- [ ] Form works
- [ ] Redirect works
- [ ] All smoke tests pass

**Time Estimate**: 20-25 minutes

---

### 📌 Milestone 9c: Migrate Daily Values to Template (30-40 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Medium
**Risk**: Medium (complex page)

**Goal**: Migrate daily values page to template with filters.

**Agent Instructions:**

**Step 1: Create `templates/pages/daily_values.html`**
- Extract HTML
- Include filter form
- Include results table
- Add Jinja2 logic for loops

**Step 2: Extract JS to `static/js/daily_values.js`**
- Any filter logic
- Any interactive features

**Step 3: Update `api/pages/daily_values.py`**
```python
return render_template('pages/daily_values.html',
    results=results,
    entities=filter_options['entities'],
    value_names=filter_options['value_names'],
    units=filter_options['units'],
    # current filter values for preserving state
    current_entity_id=entity_id,
    current_value_names=value_name_ids,
    current_unit=unit
)
```

**Step 4: Test all filters**

**Validation Checklist:**
- [ ] Template created with filters and table
- [ ] No inline HTML
- [ ] All filters work
- [ ] Results display correctly
- [ ] Filter state preserved
- [ ] All smoke tests pass

**Time Estimate**: 30-40 minutes

---

### 📌 Milestone 9d: Migrate DB Check to Template (20-25 min)

**Session Scope**: ✅ FITS IN ONE SESSION
**Complexity**: Low
**Risk**: Low

**Goal**: Complete template migration by moving db-check page.

**Agent Instructions:**

**Step 1: Create `templates/pages/db_check.html`**
**Step 2: Update `api/pages/db_check.py`**
**Step 3: Test SQL query form**

**Validation Checklist:**
- [ ] Template created
- [ ] No inline HTML remaining
- [ ] DB check works
- [ ] SQL execution works
- [ ] All smoke tests pass
- [ ] No `render_template_string` anywhere in codebase

**Time Estimate**: 20-25 minutes

---

## 🎓 Key Principles for AI Agent

### 1. **Start Each Session by Reading**
- Read this entire plan
- Read the target milestone
- Gather context from existing files

### 2. **One Milestone Per Session**
Each milestone is designed for one focused session.

### 3. **Preserve Behavior Always**
Never change functionality during refactoring.

### 4. **Test After Each Change**
Run smoke tests frequently. Fix issues immediately.

### 5. **Use Semantic Search**
Find similar patterns before creating new code.

### 6. **Verify Imports**
Test that new modules can be imported before proceeding.

### 7. **Check File Paths**
Template paths don't include "templates/" prefix.

### 8. **Session End Protocol**
- Run all smoke tests
- Report what was completed
- Note any issues for next session

---

## ✅ Session End Report Template

At the end of each session, provide this report:

```
## Milestone X Completion Report

**Status**: ✅ COMPLETE / ⚠️ PARTIAL / ❌ INCOMPLETE

**Completed:**
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

**Files Created:**
- path/to/file1.py
- path/to/file2.html

**Files Modified:**
- path/to/file3.py

**Smoke Tests:**
- [ ] All tests passed
- [ ] Found issue: [description]

**Next Session:**
Start with Milestone Y

**Notes:**
Any issues, decisions, or important context for next session.
```

---

## 📊 Progress Tracker

Mark milestones as you complete them:

- [ ] M0: Baseline Documentation (10-15 min)
- [ ] M1: Template & Static Infrastructure (20-30 min)
- [ ] M2: Migrate /admin to Templates (30-40 min)
- [ ] M3: Extract Job Manager (25-35 min)
- [ ] M4a: Split Routes - Home & Check CIK (30-40 min)
- [ ] M4b: Split Routes - Daily Values (25-35 min)
- [ ] M4c: Split Routes - Admin & DB Check (30-40 min)
- [ ] M5: Create Services Layer (25-35 min)
- [ ] M6: Create /api/v1 Endpoints (30-40 min)
- [ ] M7: Live Admin Updates (OPTIONAL) (20-30 min)
- [ ] M8: Security Hardening (25-35 min)
- [ ] M9a: Migrate Home to Template (15-20 min)
- [ ] M9b: Migrate Check CIK to Template (20-25 min)
- [ ] M9c: Migrate Daily Values to Template (30-40 min)
- [ ] M9d: Migrate DB Check to Template (20-25 min)

**Total Estimated Time**: 5-7 hours (across 15 sessions)

---

## 🎯 Success Criteria

Refactor complete when:

- [ ] All milestones checked above
- [ ] No `render_template_string()` in codebase
- [ ] All HTML in `templates/`
- [ ] All CSS in `static/css/`
- [ ] All JS in `static/js/`
- [ ] Routes split into blueprints
- [ ] Service layer exists
- [ ] Job manager extracted
- [ ] At least one `/api/v1` endpoint
- [ ] All smoke tests pass
- [ ] pytest suite passes
- [ ] Documentation updated

---

## 🚀 Quick Start

**For the AI agent:**

1. Read this entire document
2. Check progress tracker
3. Start with first unchecked milestone
4. Read that milestone completely
5. Gather context (read existing files)
6. Execute the milestone
7. Test thoroughly
8. Provide completion report
9. Wait for next session instruction

**Remember**: Working software after each session is the goal. Take your time and test thoroughly.
