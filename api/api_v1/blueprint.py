from flask import Blueprint

from api.api_v1.admin import admin_v1_bp


def create_api_v1_blueprint() -> Blueprint:
    """Create the /api/v1 blueprint and register sub-blueprints."""

    v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
    v1_bp.register_blueprint(admin_v1_bp)
    return v1_bp
