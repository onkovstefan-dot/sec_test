from flask import Blueprint, jsonify, request, render_template_string, redirect, url_for
from models.submissions_flat import SubmissionsFlat
from models.entities import Entity
from models.daily_values import DailyValue
from models.dates import DateEntry
from models.value_names import ValueName
from db import SessionLocal
from sqlalchemy import inspect

api_bp = Blueprint("api", __name__)


@api_bp.route("/", methods=["GET"])
def landing_page():
    """Landing page: select a CIK; if data exists redirect to /daily-values, else show message."""
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

        selected_entity = None
        has_data = False
        message = ""

        if cik:
            # Lookup against full entities table so a user-supplied CIK can still yield a sensible message
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
      <form method="GET" action="/">
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


@api_bp.route("/daily-values", methods=["GET"])
def daily_values_page():
    """Second page: display daily_values for a given entity_id (required)."""
    entity_id = request.args.get("entity_id", type=int)

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

        rows = (
            session.query(DailyValue, DateEntry, ValueName)
            .join(DateEntry, DailyValue.date_id == DateEntry.id)
            .join(ValueName, DailyValue.value_name_id == ValueName.id)
            .filter(DailyValue.entity_id == entity_id)
            .order_by(DateEntry.date, ValueName.name)
            .all()
        )

        # JSON response (kept for API use)
        if request.accept_mimetypes.best == "application/json":
            result = [
                {
                    "entity_id": entity_id,
                    "cik": entity.cik,
                    "date": str(dv_date.date),
                    "value_name": vn.name,
                    "value": dv.value,
                }
                for dv, dv_date, vn in rows
            ]
            return jsonify(result)

        table_rows_html = "".join(
            f"<tr><td>{str(dv_date.date)}</td><td>{vn.name}</td>"
            f"<td class='num'>{dv.value}</td></tr>"
            for dv, dv_date, vn in rows
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Daily Values  {entity.cik}</title>
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

      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Value Name</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {table_rows_html if table_rows_html else '<tr><td colspan="3" class="empty">No records found.</td></tr>'}
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
