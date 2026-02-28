import os
import time

from flask import Blueprint, redirect, render_template, request, url_for

from api.jobs.manager import (
    populate_daily_values_job,
    recreate_sqlite_db_job,
    read_last_log_line,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/init-db", methods=["POST"])
def admin_init_db():
    """Create missing tables on demand."""
    from db import Base, engine

    Base.metadata.create_all(bind=engine)
    return redirect(url_for("api.admin.admin_page"))


@admin_bp.route("/recreate-db", methods=["POST"])
def admin_recreate_db():
    """Recreate SQLite DB in the background (destructive)."""
    # Require confirmation token to reduce accidental clicks.
    confirm = (request.form.get("confirm") or "").strip().upper()
    if confirm != "RECREATE":
        recreate_sqlite_db_job.set_error(
            "Refused to recreate DB: missing/invalid confirmation. "
            "Type RECREATE in the confirmation box and submit again."
        )
        return redirect(url_for("api.admin.admin_page"))

    recreate_sqlite_db_job.start()
    return redirect(url_for("api.admin.admin_page"))


@admin_bp.route("/stop-populate", methods=["POST"])
def admin_stop_populate():
    """Request stopping the populate_daily_values job.

    This is cooperative; if the script is already running, it may not stop until it finishes.
    """
    populate_daily_values_job.request_stop()
    return redirect(url_for("api.admin.admin_page"))


@admin_bp.route("/", methods=["GET", "POST"])
@admin_bp.route("", methods=["GET", "POST"])
def admin_page():
    """Admin page: start background populate_daily_values job."""
    started = None
    if request.method == "POST":
        started = populate_daily_values_job.start()

    state = populate_daily_values_job.get_state()
    recreate_state = recreate_sqlite_db_job.get_state()

    # Last log line(s)
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    logs_dir = os.path.join(repo_root, "logs")
    populate_log_path = os.path.join(logs_dir, "utils_populate_daily_values.log")
    populate_last_log = read_last_log_line(populate_log_path)

    # recreate_sqlite_db uses the shared logger too (app logs) unless you add a dedicated one.
    recreate_log_path = os.path.join(logs_dir, "app.log")
    recreate_last_log = read_last_log_line(recreate_log_path)

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

    recreate_status = "RUNNING" if recreate_state["running"] else "IDLE"
    recreate_started_at = fmt_ts(recreate_state.get("started_at"))
    recreate_ended_at = fmt_ts(recreate_state.get("ended_at"))
    recreate_error = recreate_state.get("error") or ""

    def esc(s: str) -> str:
        return (
            (s or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    return render_template(
        "pages/admin.html",
        # messaging
        msg=msg,
        # populate job
        state=state,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        populate_last_log=populate_last_log,
        error=error,
        # recreate job
        recreate_state=recreate_state,
        recreate_status=recreate_status,
        recreate_started_at=recreate_started_at,
        recreate_ended_at=recreate_ended_at,
        recreate_last_log=recreate_last_log,
        recreate_error=recreate_error,
        # helpers
        esc=esc,
    )
