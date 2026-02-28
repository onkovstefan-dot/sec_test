from flask import Blueprint, jsonify, request, render_template

from db import SessionLocal
from sqlalchemy import inspect


db_check_bp = Blueprint("db_check", __name__)


@db_check_bp.route("/db-check", methods=["GET"])
@db_check_bp.route("/sql", methods=["GET"])
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
                from sqlalchemy import text

                columns = [c["name"] for c in inspector.get_columns(selected_table)]
                result = session.execute(
                    text(f'SELECT * FROM "{selected_table}" LIMIT :limit'),
                    {"limit": limit},
                )
                rows = [dict(r._mapping) for r in result]
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

        return (
            render_template(
                "pages/db_check.html",
                tables=tables,
                selected_table=selected_table,
                limit=limit,
                limit_raw=limit_raw,
                columns=columns,
                rows=rows,
                error=error,
            ),
            200,
        )
    finally:
        session.close()
