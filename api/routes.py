import os
import sys
import time

# Allow running this module directly (or via certain runners) without package context.
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from sqlalchemy import inspect

from api.jobs.manager import (
    populate_daily_values_job,
    read_last_log_line,
    recreate_sqlite_db_job,
)
from db import SessionLocal
from models.daily_values import DailyValue
from models.dates import DateEntry
from models.entities import Entity
from models.units import Unit
from models.value_names import ValueName
from utils.value_parsing import parse_primitive

api_bp = Blueprint("api", __name__)

# NOTE (Milestone 4a): the following routes were migrated to `api/pages/*` and are
# registered via `api/blueprint.py`:
# - GET /
# - GET /check-cik
# Keep this file for reference until the full route split is complete.


# @api_bp.route("/", methods=["GET"])
# def home_page():
#     ...migrated to api/pages/home.py...
#
# @api_bp.route("/check-cik", methods=["GET"])
# def check_cik_page():
#     ...migrated to api/pages/check_cik.py...


# NOTE (Milestone 4c): the following routes were migrated to `api/pages/admin.py`
# and are registered via `api/blueprint.py` (as `admin_bp`, url_prefix='/admin'):
# - POST /admin/init-db
# - POST /admin/recreate-db
# - POST /admin/stop-populate
# - GET/POST /admin

# @api_bp.route("/admin/init-db", methods=["POST"])
# def admin_init_db():
#     ...migrated to api/pages/admin.py...
#
# @api_bp.route("/admin/recreate-db", methods=["POST"])
# def admin_recreate_db():
#     ...migrated to api/pages/admin.py...
#
# @api_bp.route("/admin/stop-populate", methods=["POST"])
# def admin_stop_populate():
#     ...migrated to api/pages/admin.py...
#
# @api_bp.route("/admin", methods=["GET", "POST"])
# def admin_page():
#     ...migrated to api/pages/admin.py...


# NOTE (Milestone 4b): the following route was migrated to `api/pages/daily_values.py`
# and is registered via `api/blueprint.py`:
# - GET /daily-values


# @api_bp.route("/daily-values", methods=["GET"])
# def daily_values_page():
#     ...migrated to api/pages/daily_values.py...


# NOTE (Milestone 4c): the following routes were migrated to `api/pages/db_check.py`
# and are registered via `api/blueprint.py` (as `db_check_bp`):
# - GET /db-check
# - GET /sql

# @api_bp.route("/db-check", methods=["GET"])
# @api_bp.route("/sql", methods=["GET"])
# def db_check():
#     ...migrated to api/pages/db_check.py...


# ...existing code...
