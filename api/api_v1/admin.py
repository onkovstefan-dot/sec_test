from __future__ import annotations

from flask import Blueprint, jsonify

from api.jobs.manager import populate_daily_values_job, recreate_sqlite_db_job
from api.schemas.api_responses import ok

admin_v1_bp = Blueprint("admin_v1", __name__, url_prefix="/admin")


@admin_v1_bp.get("/jobs")
def get_jobs():
    """Return current background job state for the admin UI."""

    data = {
        "populate_daily_values": populate_daily_values_job.get_state(),
        "recreate_sqlite_db": recreate_sqlite_db_job.get_state(),
    }
    return jsonify(ok(data))
