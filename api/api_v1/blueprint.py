from flask import Blueprint


def create_api_v1_blueprint() -> Blueprint:
    """Create the /api/v1 blueprint and register sub-blueprints."""

    v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
    return v1_bp
