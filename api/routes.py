import os
import sys
import threading
import time
import traceback

# Allow running this module directly (or via certain runners) without package context.
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from flask import Blueprint, jsonify, request, render_template_string, redirect, url_for
from models.entities import Entity
from models.daily_values import DailyValue
from models.dates import DateEntry
from models.value_names import ValueName
from models.units import Unit
from db import SessionLocal
from sqlalchemy import inspect

from utils.value_parsing import parse_primitive

api_bp = Blueprint("api", __name__)


def _read_last_log_line(log_path: str, *, max_bytes: int = 64 * 1024) -> str:
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


# In-process background job state for populate_daily_values
_populate_job_lock = threading.Lock()
_populate_job_state = {
    "running": False,
    "started_at": None,
    "ended_at": None,
    "error": None,
    "stop_requested": False,
}

# In-process background job state for recreate_sqlite_db
_recreate_job_lock = threading.Lock()
_recreate_job_state = {
    "running": False,
    "started_at": None,
    "ended_at": None,
    "error": None,
}


def _start_populate_daily_values_background() -> bool:
    """Start utils.populate_daily_values.main() in a daemon thread.

    Returns True if a new job was started, False if one is already running.
    """

    with _populate_job_lock:
        if _populate_job_state["running"]:
            return False
        _populate_job_state.update(
            {
                "running": True,
                "started_at": time.time(),
                "ended_at": None,
                "error": None,
                "stop_requested": False,
            }
        )

    def _runner():
        try:
            # Lazily ensure schema exists before running the job.
            from db import Base, engine

            Base.metadata.create_all(bind=engine)

            from utils import populate_daily_values

            # NOTE: populate_daily_values.main() is not currently designed to be interruptible.
            # This stop flag is cooperative and will only prevent a new run from starting.
            with _populate_job_lock:
                if _populate_job_state.get("stop_requested"):
                    return

            populate_daily_values.main()
        except Exception:
            with _populate_job_lock:
                _populate_job_state["error"] = traceback.format_exc()
        finally:
            with _populate_job_lock:
                _populate_job_state["running"] = False
                _populate_job_state["ended_at"] = time.time()

    t = threading.Thread(target=_runner, name="populate_daily_values", daemon=True)
    t.start()
    return True


def _start_recreate_sqlite_db_background() -> bool:
    """Start utils.recreate_sqlite_db.main() in a daemon thread.

    Returns True if started, False if already running.

    WARNING: This is destructive (deletes data/sec.db).
    """
    with _recreate_job_lock:
        if _recreate_job_state["running"]:
            return False
        _recreate_job_state.update(
            {
                "running": True,
                "started_at": time.time(),
                "ended_at": None,
                "error": None,
            }
        )

    def _runner():
        try:
            from utils import recreate_sqlite_db

            recreate_sqlite_db.main()
        except Exception:
            with _recreate_job_lock:
                _recreate_job_state["error"] = traceback.format_exc()
        finally:
            with _recreate_job_lock:
                _recreate_job_state["running"] = False
                _recreate_job_state["ended_at"] = time.time()

    t = threading.Thread(target=_runner, name="recreate_sqlite_db", daemon=True)
    t.start()
    return True


@api_bp.route("/admin/init-db", methods=["POST"])
def admin_init_db():
    """Create missing tables on demand."""
    from db import Base, engine

    Base.metadata.create_all(bind=engine)
    return redirect(url_for("api.admin_page"))


@api_bp.route("/admin/recreate-db", methods=["POST"])
def admin_recreate_db():
    """Recreate SQLite DB in the background (destructive)."""
    # Require confirmation token to reduce accidental clicks.
    confirm = (request.form.get("confirm") or "").strip().upper()
    if confirm != "RECREATE":
        with _recreate_job_lock:
            _recreate_job_state["error"] = (
                "Refused to recreate DB: missing/invalid confirmation. "
                "Type RECREATE in the confirmation box and submit again."
            )
        return redirect(url_for("api.admin_page"))

    _start_recreate_sqlite_db_background()
    return redirect(url_for("api.admin_page"))


@api_bp.route("/admin/stop-populate", methods=["POST"])
def admin_stop_populate():
    """Request stopping the populate_daily_values job.

    This is cooperative; if the script is already running, it may not stop until it finishes.
    """
    with _populate_job_lock:
        _populate_job_state["stop_requested"] = True
    return redirect(url_for("api.admin_page"))


@api_bp.route("/", methods=["GET"])
def home_page():
    """Home page: choose between CIK data explorer and admin tools."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Daily Values  Home</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #f5f7fa; color: #1a1a2e; }}
    header {{ background: #16213e; color: #fff; padding: 1rem 2rem; }}
    header h1 {{ margin: 0; font-size: 1.4rem; letter-spacing: .5px; }}
    main {{ max-width: 900px; margin: 2rem auto; padding: 0 1.5rem; }}
    .card {{ background: #fff; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,.08); padding: 1.5rem 2rem; }}
    .actions {{ display: grid; grid-template-columns: 1fr; gap: 1rem; margin-top: 1rem; }}
    @media (min-width: 720px) {{ .actions {{ grid-template-columns: 1fr 1fr; }} }}
    a.bigbutton {{
      display: block;
      padding: .45rem 1.2rem; background: #0f3460; color: #fff;
      border: none; border-radius: 10px; font-size: 1.0rem; cursor: pointer;
      transition: background .2s;
      text-decoration: none;
      text-align: center;
      padding: 1rem 1.25rem;
    }}
    a.bigbutton:hover {{ background: #16213e; }}
    .sub {{ color: #666; margin-top: .35rem; font-size: .95rem; }}
  </style>
</head>
<body>
  <header><h1>Daily Values Explorer</h1></header>
  <main>
    <div class="card">
      <div class="actions">
        <div>
          <a class="bigbutton" href="/check-cik">Check CIK data</a>
          <div class="sub">Pick a CIK and browse daily values.</div>
        </div>
        <div>
          <a class="bigbutton" href="/admin">Admin page</a>
          <div class="sub">Run data population while the app is running.</div>
        </div>
      </div>
    </div>
  </main>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html"}


@api_bp.route("/check-cik", methods=["GET"])
def check_cik_page():
    """CIK selection page: if data exists redirect to /daily-values, else show message."""
    cik = request.args.get("cik", "").strip()

    session = SessionLocal()
    try:
        # Only show entities that actually have at least one daily_values row
        entities = (
            session.query(Entity)
            .join(DailyValue, DailyValue.entity_id == Entity.id)
            .distinct()
            .order_by(Entity.cik)
            .all()
        )

        message = ""
        if cik:
            selected_entity = session.query(Entity).filter(Entity.cik == cik).first()
            if not selected_entity:
                message = f"No entity found for CIK '{cik}'."
            else:
                has_data = (
                    session.query(DailyValue.id)
                    .filter(DailyValue.entity_id == selected_entity.id)
                    .limit(1)
                    .first()
                    is not None
                )
                if has_data:
                    return redirect(
                        url_for("api.daily_values_page", entity_id=selected_entity.id)
                    )
                message = f"No daily values found for CIK '{cik}'."

        entity_options = "".join(
            f'<option value="{e.cik}" {"selected" if e.cik == cik else ""}>'
            f"{e.cik}</option>"
            for e in entities
        )

        banner_html = f'<p class="error">{message}</p>' if message else ""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Daily Values  Select CIK</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #f5f7fa; color: #1a1a2e; }}
    header {{ background: #16213e; color: #fff; padding: 1rem 2rem; }}
    header h1 {{ margin: 0; font-size: 1.4rem; letter-spacing: .5px; }}
    main {{ max-width: 900px; margin: 2rem auto; padding: 0 1.5rem; }}
    .card {{ background: #fff; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,.08); padding: 1.5rem 2rem; }}
    .toolbar {{ display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 1rem; margin-bottom: 1rem; }}
    a.button {{
      display: inline-block; padding: .45rem 1.0rem; background: #0f3460; color: #fff;
      text-decoration: none; border-radius: 6px; font-size: .95rem;
    }}
    a.button:hover {{ background: #16213e; }}
    form {{ display: flex; gap: .75rem; align-items: center; flex-wrap: wrap; margin-bottom: 1rem; }}
    label {{ font-weight: 600; font-size: .9rem; }}
    select {{
      padding: .45rem .75rem; border: 1px solid #c8d0db; border-radius: 6px;
      font-size: .95rem; background: #f9fafb; min-width: 240px;
    }}
    button {{
      padding: .45rem 1.2rem; background: #0f3460; color: #fff;
      border: none; border-radius: 6px; font-size: .95rem; cursor: pointer;
      transition: background .2s;
    }}
    button:hover {{ background: #16213e; }}
    p.hint {{ color: #666; margin: 0.75rem 0 0; }}
    p.error {{ color: #c0392b; font-weight: 600; margin: 0.75rem 0 0; }}
  </style>
</head>
<body>
  <header><h1>Daily Values Explorer</h1></header>
  <main>
    <div class="card">
      <div class="toolbar">
        <div class="hint">Choose a CIK that has at least one daily value.</div>
        <div><a class="button" href="/">Home</a></div>
      </div>
      <form method="GET" action="/check-cik">
        <label for="cik">Select CIK:</label>
        <select id="cik" name="cik" required>
          <option value="">-- select a CIK --</option>
          {entity_options}
        </select>
        <button type="submit">Continue</button>
      </form>
      {banner_html}
      <p class="hint">After selection, youll be redirected to the daily values page if data exists.</p>
    </div>
  </main>
</body>
</html>"""
        return html, 200, {"Content-Type": "text/html"}
    finally:
        session.close()


@api_bp.route("/admin", methods=["GET", "POST"])
def admin_page():
    """Admin page: start background populate_daily_values job."""
    started = None
    if request.method == "POST":
        started = _start_populate_daily_values_background()

    with _populate_job_lock:
        state = dict(_populate_job_state)

    with _recreate_job_lock:
        recreate_state = dict(_recreate_job_state)

    # Last log line(s)
    repo_root = os.path.dirname(os.path.dirname(__file__))
    populate_log_path = os.path.join(repo_root, "populate_daily_values.log")
    populate_last_log = _read_last_log_line(populate_log_path)
    # recreate_sqlite_db prints to stdout; we don't have a dedicated log file.
    # Reuse the same shared log file if you redirect output there in the future.
    recreate_last_log = _read_last_log_line(populate_log_path)

    def fmt_ts(ts):
        if not ts:
            return ""
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

    status = "RUNNING" if state["running"] else "IDLE"
    started_at = fmt_ts(state.get("started_at"))
    ended_at = fmt_ts(state.get("ended_at"))
    error = state.get("error") or ""
    msg = ""
    if started is True:
        msg = "Started populate_daily_values in the background."
    elif started is False:
        msg = "A populate_daily_values job is already running."

    msg_html = f'<p class="msg">{msg}</p>' if msg else ""
    error_html = f"<pre class='error'>{error}</pre>" if error else ""

    recreate_status = "RUNNING" if recreate_state["running"] else "IDLE"
    recreate_started_at = fmt_ts(recreate_state.get("started_at"))
    recreate_ended_at = fmt_ts(recreate_state.get("ended_at"))
    recreate_error = recreate_state.get("error") or ""
    recreate_error_html = (
        f"<pre class='error'>{recreate_error}</pre>" if recreate_error else ""
    )

    def esc(s: str) -> str:
        return (
            (s or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Admin</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #f5f7fa; color: #1a1a2e; }}
    header {{ background: #16213e; color: #fff; padding: 1rem 2rem; }}
    header h1 {{ margin: 0; font-size: 1.4rem; letter-spacing: .5px; }}
    main {{ max-width: 900px; margin: 2rem auto; padding: 0 1.5rem; }}
    .card {{ background: #fff; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,.08); padding: 1.5rem 2rem; }}
    .toolbar {{ display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 1rem; margin-bottom: 1rem; }}
    a.button {{
      display: inline-block; padding: .45rem 1.0rem; background: #0f3460; color: #fff;
      text-decoration: none; border-radius: 6px; font-size: .95rem;
    }}
    a.button:hover {{ background: #16213e; }}
    button {{
      padding: .55rem 1.2rem; background: #0f3460; color: #fff;
      border: none; border-radius: 6px; font-size: .95rem; cursor: pointer;
      transition: background .2s;
    }}
    button:hover {{ background: #16213e; }}
    .hint {{ color: #666; }}
    .kv {{ display: grid; grid-template-columns: 160px 1fr; gap: .35rem .75rem; margin: 1rem 0; }}
    .k {{ color: #444; font-weight: 700; }}
    .v {{ color: #222; }}
    .msg {{ color: #0f3460; font-weight: 700; }}
    pre.error {{ background: #fff5f5; border: 1px solid #ffd6d6; color: #8b0000; padding: .75rem; overflow: auto; border-radius: 8px; }}
    .warn {{
      background: #fff8e6;
      border: 1px solid #ffe0a3;
      color: #7a4b00;
      padding: .75rem .9rem;
      border-radius: 10px;
      margin: .5rem 0 .75rem;
      line-height: 1.3;
    }}
    .danger {{ background: #b00020; }}
    .danger:hover {{ background: #7c0016; }}
    input.confirm {{
      padding: .45rem .65rem;
      border: 1px solid #c8d0db;
      border-radius: 6px;
      font-size: .95rem;
      background: #fff;
      min-width: 220px;
      margin-right: .5rem;
    }}
  </style>
</head>
<body>
  <header><h1>Admin</h1></header>
  <main>
    <div class="card">
      <div class="toolbar">
        <div class="hint">Run maintenance tasks.</div>
        <div><a class="button" href="/">Home</a></div>
      </div>

      {msg_html}

      <form method="POST" action="/admin/init-db" style="margin-bottom: .75rem;">
        <button type="submit">Initialize DB schema</button>
      </form>

      <form method="POST" action="/admin/recreate-db" style="margin-bottom: .75rem;" onsubmit="return confirm('This will DELETE data/sec.db and recreate an empty schema.\n\nType RECREATE in the box and click OK to proceed.');">
        <div class="warn">
          <strong>Warning:</strong> This deletes <code>data/sec.db</code> and recreates an empty DB.
          This cannot be undone.
        </div>
        <input class="confirm" name="confirm" placeholder="Type RECREATE to confirm" autocomplete="off" />
        <button class="danger" type="submit" {"disabled" if recreate_state["running"] else ""}>
          Recreate SQLite DB (destructive)
        </button>
      </form>

      <form method="POST" action="/admin">
        <button type="submit" {"disabled" if state["running"] else ""}>
          Start populate_daily_values
        </button>
      </form>

      <form method="POST" action="/admin/stop-populate" style="margin-top: .5rem;">
        <button type="submit" {"disabled" if not state["running"] else ""}>
          Stop populate_daily_values
        </button>
      </form>

      <div class="kv">
        <div class="k">Status</div><div class="v">{status}</div>
        <div class="k">Started</div><div class="v">{started_at or '-'}</div>
        <div class="k">Ended</div><div class="v">{ended_at or '-'}</div>
        <div class="k">Stop requested</div><div class="v">{'YES' if state.get('stop_requested') else 'NO'}</div>
        <div class="k">Last log line</div><div class="v"><code>{esc(populate_last_log)}</code></div>
      </div>

      <div class="kv" style="margin-top: 1.25rem;">
        <div class="k">Recreate DB</div><div class="v">{recreate_status}</div>
        <div class="k">Started</div><div class="v">{recreate_started_at or '-'}</div>
        <div class="k">Ended</div><div class="v">{recreate_ended_at or '-'}</div>
        <div class="k">Last log line</div><div class="v"><code>{esc(recreate_last_log)}</code></div>
      </div>

      <div class="hint">Logs are written to <code>populate_daily_values.log</code>.</div>
      {error_html}
      {recreate_error_html}
    </div>
  </main>
</body>
</html>"""
    return html, 200, {"Content-Type": "text/html"}


@api_bp.route("/daily-values", methods=["GET"])
def daily_values_page():
    """Second page: display daily_values for a given entity_id (required)."""
    entity_id = request.args.get("entity_id", type=int)

    # Optional filters
    value_name_filters = [
        v.strip() for v in request.args.getlist("value_name") if v and v.strip()
    ]
    unit_filter = (request.args.get("unit") or "").strip()

    session = SessionLocal()
    try:
        if not entity_id:
            return (
                "Missing required query param: entity_id",
                400,
                {"Content-Type": "text/plain"},
            )

        entity = session.query(Entity).filter(Entity.id == entity_id).first()
        if not entity:
            return (
                f"No entity found for entity_id={entity_id}",
                404,
                {"Content-Type": "text/plain"},
            )

        # Build dropdown options (restricted to this entity's available values)
        value_name_options = [
            r[0]
            for r in (
                session.query(ValueName.name)
                .join(DailyValue, DailyValue.value_name_id == ValueName.id)
                .filter(DailyValue.entity_id == entity_id)
                .distinct()
                .order_by(ValueName.name)
                .all()
            )
        ]

        unit_options = [
            r[0]
            for r in (
                session.query(Unit.name)
                .join(ValueName, ValueName.unit_id == Unit.id)
                .join(DailyValue, DailyValue.value_name_id == ValueName.id)
                .filter(DailyValue.entity_id == entity_id)
                .distinct()
                .order_by(Unit.name)
                .all()
            )
        ]

        query = (
            session.query(DailyValue, DateEntry, ValueName, Unit)
            .join(DateEntry, DailyValue.date_id == DateEntry.id)
            .join(ValueName, DailyValue.value_name_id == ValueName.id)
            .outerjoin(Unit, ValueName.unit_id == Unit.id)
            .filter(DailyValue.entity_id == entity_id)
        )

        # Apply filters (ignore values not present in options to avoid surprising results)
        valid_value_name_filters = [
            vn for vn in value_name_filters if vn in value_name_options
        ]
        if valid_value_name_filters:
            query = query.filter(ValueName.name.in_(valid_value_name_filters))
        value_name_filters = valid_value_name_filters

        if unit_filter and unit_filter in unit_options:
            query = query.filter(Unit.name == unit_filter)
        else:
            unit_filter = ""

        rows = query.order_by(DateEntry.date, ValueName.name).all()

        # JSON response (kept for API use)
        if request.accept_mimetypes.best == "application/json":
            result = [
                {
                    "entity_id": entity_id,
                    "cik": entity.cik,
                    "date": str(dv_date.date),
                    "value_name": vn.name,
                    "unit": (unit.name if unit else "NA"),
                    "value": parse_primitive(dv.value),
                }
                for dv, dv_date, vn, unit in rows
            ]
            return jsonify(result)

        table_rows_html = "".join(
            f"<tr><td>{str(dv_date.date)}</td><td>{vn.name}</td><td>{(unit.name if unit else 'NA')}</td>"
            f"<td class='num'>{parse_primitive(dv.value)}</td></tr>"
            for dv, dv_date, vn, unit in rows
        )

        value_name_options_html = "".join(
            f'<option value="{vn}" {"selected" if vn in value_name_filters else ""}>{vn}</option>'
            for vn in value_name_options
        )

        unit_options_html = "".join(
            f'<option value="{u}" {"selected" if u == unit_filter else ""}>{u}</option>'
            for u in unit_options
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Daily Values  {entity.cik}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #f5f7fa; color: #1a1a2e; }}
    header {{ background: #16213e; color: #fff; padding: 1rem 2rem; }}
    header h1 {{ margin: 0; font-size: 1.4rem; letter-spacing: .5px; }}
    main {{ max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }}
    .card {{ background: #fff; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,.08); padding: 1.5rem 2rem; }}
    .topbar {{ display: flex; gap: 1rem; align-items: center; justify-content: space-between; flex-wrap: wrap; margin-bottom: 1rem; }}
    a.button {{
      display: inline-block; padding: .45rem 1.0rem; background: #0f3460; color: #fff;
      text-decoration: none; border-radius: 6px; font-size: .95rem;
    }}
    a.button:hover {{ background: #16213e; }}

    .filters {{
      display: flex; gap: .75rem; flex-wrap: wrap; align-items: end;
      margin: 0 0 1rem 0;
    }}
    .filters label {{ font-weight: 600; font-size: .85rem; display: block; margin-bottom: .25rem; color: #333; }}
    .filters select {{
      padding: .45rem .75rem; border: 1px solid #c8d0db; border-radius: 6px;
      font-size: .95rem; background: #f9fafb; min-width: 240px;
    }}
    .filters button {{
      padding: .45rem 1.2rem; background: #0f3460; color: #fff;
      border: none; border-radius: 6px; font-size: .95rem; cursor: pointer;
      transition: background .2s;
      height: 2.35rem;
    }}
    .filters button:hover {{ background: #16213e; }}
    .filters a.link {{ color: #0f3460; text-decoration: none; font-size: .95rem; padding: .45rem 0; }}
    .filters a.link:hover {{ text-decoration: underline; }}

    table {{ width: 100%; border-collapse: collapse; font-size: .9rem; }}
    th {{ background: #0f3460; color: #fff; padding: .55rem .9rem; text-align: left; }}
    td {{ padding: .5rem .9rem; border-bottom: 1px solid #eef0f4; }}
    tr:hover td {{ background: #f0f4ff; }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    td.empty {{ text-align: center; color: #888; padding: 1.5rem; }}
    .meta {{ color: #555; font-size: .95rem; }}
  </style>
</head>
<body>
  <header><h1>Daily Values Explorer</h1></header>
  <main>
    <div class="card">
      <div class="topbar">
        <div class="meta">
          <strong>CIK:</strong> {entity.cik} &nbsp; <strong>Entity ID:</strong> {entity_id}
        </div>
        <div>
          <a class="button" href="/">Change CIK</a>
        </div>
      </div>

      <form class="filters" method="GET" action="/daily-values">
        <input type="hidden" name="entity_id" value="{entity_id}" />
        <div>
          <label for="value_name">Value Name</label>
          <select id="value_name" name="value_name" multiple size="6">
            {value_name_options_html}
          </select>
        </div>
        <div>
          <label for="unit">Unit</label>
          <select id="unit" name="unit">
            <option value="">All</option>
            {unit_options_html}
          </select>
        </div>
        <button type="submit">Apply</button>
        <a class="link" href="/daily-values?entity_id={entity_id}">Clear</a>
      </form>

      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Value Name</th>
            <th>Unit</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {table_rows_html if table_rows_html else '<tr><td colspan="4" class="empty">No records found.</td></tr>'}
        </tbody>
      </table>
    </div>
  </main>
</body>
</html>"""
        return html, 200, {"Content-Type": "text/html"}
    finally:
        session.close()


@api_bp.route("/db-check", methods=["GET"])
@api_bp.route("/sql", methods=["GET"])
def db_check():
    """Simple DB inspector: pick a table and preview up to N rows (default 10)."""
    table = (request.args.get("table") or "").strip()
    limit_raw = (request.args.get("limit") or "").strip()
    try:
        limit = int(limit_raw) if limit_raw else 10
    except ValueError:
        limit = 10

    # Safety bounds
    if limit < 1:
        limit = 1
    if limit > 500:
        limit = 500

    session = SessionLocal()
    try:
        # Discover tables from SQLAlchemy engine
        inspector = inspect(session.bind)
        tables = sorted(inspector.get_table_names())

        selected_table = table if table in tables else (tables[0] if tables else "")

        rows = []
        columns = []
        error = ""

        if selected_table:
            try:
                columns = [c["name"] for c in inspector.get_columns(selected_table)]
                # Use parameterized LIMIT; table name is validated against introspected list
                result = session.execute(
                    inspect(session.bind).dialect.statement_compiler(
                        inspect(session.bind).dialect, None
                    )
                )
            except Exception:
                # Fallback to a safe raw query path
                try:
                    from sqlalchemy import text

                    result = session.execute(
                        text(f'SELECT * FROM "{selected_table}" LIMIT :limit'),
                        {"limit": limit},
                    )
                    rows = [dict(r._mapping) for r in result]
                    if not columns and rows:
                        columns = list(rows[0].keys())
                except Exception as e:
                    error = str(e)

        # JSON response
        if request.accept_mimetypes.best == "application/json":
            return jsonify(
                {
                    "tables": tables,
                    "selected_table": selected_table,
                    "limit": limit,
                    "columns": columns,
                    "rows": rows,
                    "error": error,
                }
            )

        options_html = "".join(
            f'<option value="{t}" {"selected" if t == selected_table else ""}>{t}</option>'
            for t in tables
        )

        error_html = f'<p class="error">{error}</p>' if error else ""

        if rows and columns:
            header_html = "".join(f"<th>{c}</th>" for c in columns)
            body_html = "".join(
                "<tr>"
                + "".join(
                    f"<td>{(row.get(c) if row.get(c) is not None else '')}</td>"
                    for c in columns
                )
                + "</tr>"
                for row in rows
            )
            table_html = f"""
            <table>
              <thead><tr>{header_html}</tr></thead>
              <tbody>{body_html}</tbody>
            </table>
            """
        else:
            table_html = '<p class="hint">No rows to display.</p>'

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DB Check</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #f5f7fa; color: #1a1a2e; }}
    header {{ background: #16213e; color: #fff; padding: 1rem 2rem; }}
    header h1 {{ margin: 0; font-size: 1.4rem; letter-spacing: .5px; }}
    main {{ max-width: 1200px; margin: 2rem auto; padding: 0 1.5rem; }}
    .card {{ background: #fff; border-radius: 10px; box-shadow: 0 2px 12px rgba(0,0,0,.08); padding: 1.5rem 2rem; }}
    form {{ display: flex; gap: .75rem; align-items: end; flex-wrap: wrap; margin-bottom: 1rem; }}
    label {{ font-weight: 600; font-size: .9rem; display: block; margin-bottom: .25rem; }}
    select, input[type=number] {{
      padding: .45rem .75rem; border: 1px solid #c8d0db; border-radius: 6px;
      font-size: .95rem; background: #f9fafb; min-width: 240px;
    }}
    input[type=number] {{ min-width: 140px; }}
    button {{
      padding: .45rem 1.2rem; background: #0f3460; color: #fff;
      border: none; border-radius: 6px; font-size: .95rem; cursor: pointer;
      transition: background .2s;
      height: 2.35rem;
    }}
    button:hover {{ background: #16213e; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
    th {{ position: sticky; top: 0; background: #0f3460; color: #fff; padding: .55rem .7rem; text-align: left; }}
    td {{ padding: .45rem .7rem; border-bottom: 1px solid #eef0f4; vertical-align: top; }}
    tr:hover td {{ background: #f0f4ff; }}
    .hint {{ color: #666; }}
    .error {{ color: #c0392b; font-weight: 600; }}
    .toolbar {{ display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 1rem; margin-bottom: 1rem; }}
    a.button {{
      display: inline-block; padding: .45rem 1.0rem; background: #0f3460; color: #fff;
      text-decoration: none; border-radius: 6px; font-size: .95rem;
    }}
    a.button:hover {{ background: #16213e; }}
  </style>
</head>
<body>
  <header><h1>DB Check</h1></header>
  <main>
    <div class="card">
      <div class="toolbar">
        <div class="hint">Preview raw rows from any table (limit defaults to 10 if empty).</div>
        <div><a class="button" href="/">Home</a></div>
      </div>
      <form method="GET" action="/db-check">
        <div>
          <label for="table">Table</label>
          <select id="table" name="table">{options_html}</select>
        </div>
        <div>
          <label for="limit">Limit</label>
          <input id="limit" name="limit" type="number" min="1" max="500" placeholder="10" value="{limit_raw}" />
        </div>
        <button type="submit">Load</button>
      </form>
      {error_html}
      {table_html}
    </div>
  </main>
</body>
</html>"""
        return html, 200, {"Content-Type": "text/html"}
    finally:
        session.close()
