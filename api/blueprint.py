from flask import Blueprint

from api.pages.home import home_bp
from api.pages.check_cik import check_cik_bp
from api.pages.daily_values import daily_values_bp
from api.pages.admin import admin_bp
from api.pages.db_check import db_check_bp
from api.api_v1.blueprint import create_api_v1_blueprint


def create_api_blueprint(
    *, enable_admin: bool = True, enable_db_check: bool = True
) -> Blueprint:
    """Create the main API blueprint and register page blueprints.

    Keep this as the single registration point to avoid double-registering routes.
    """
    api_bp = Blueprint("api", __name__)

    api_bp.register_blueprint(home_bp)
    api_bp.register_blueprint(check_cik_bp)
    api_bp.register_blueprint(daily_values_bp)

    if enable_admin:
        api_bp.register_blueprint(admin_bp)

    if enable_db_check:
        api_bp.register_blueprint(db_check_bp)

    # Versioned API
    api_bp.register_blueprint(create_api_v1_blueprint())

    return api_bp
