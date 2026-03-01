import os
import time

from flask import Flask, render_template, request

from api.blueprint import create_api_blueprint
from config import configure_logging
from db import Base, engine
from logging_utils import configure_app_logging, get_logger


def init_db() -> None:
    """Initialize DB schema.

    Kept out of default startup path to minimize app spin-up time.
    """

    Base.metadata.create_all(bind=engine)


def create_app() -> Flask:
    app = Flask(__name__)

    # Load config from file.
    app.config.from_pyfile("settings.py")

    # Configure unified app logging (UTC timestamps, per-file logs, daily rotation)
    configure_app_logging(app.config.get("LOG_LEVEL", "INFO"))
    logger = get_logger(__name__)

    # Keep legacy call for compatibility; it now delegates to configure_app_logging.
    configure_logging(app.logger, app.config.get("LOG_LEVEL", "INFO"))

    # --- slow request logging (opt-in by threshold; default 250ms) ---
    # Set to "0" to disable (or keep it low temporarily when investigating perf).
    slow_ms = int(os.getenv("SLOW_REQUEST_MS", "250") or "250")

    @app.before_request
    def _start_timer():
        if slow_ms > 0:
            request.environ["_req_start_ns"] = time.perf_counter_ns()

    @app.after_request
    def _log_slow_requests(resp):
        if slow_ms <= 0:
            return resp

        start_ns = request.environ.get("_req_start_ns")
        if not start_ns:
            return resp

        elapsed_ms = (time.perf_counter_ns() - int(start_ns)) / 1_000_000.0
        if elapsed_ms >= slow_ms:
            # Keep it compact and stable for grepping.
            logger.warning(
                "SLOW_REQUEST ms=%.1f status=%s method=%s path=%s query=%s",
                elapsed_ms,
                getattr(resp, "status_code", "?"),
                request.method,
                request.path,
                request.query_string.decode("utf-8", errors="replace"),
            )
        return resp

    # Register routes/blueprints (respect feature flags)
    app.register_blueprint(
        create_api_blueprint(
            enable_admin=app.config.get("ENABLE_ADMIN", True),
            enable_db_check=app.config.get("ENABLE_DB_CHECK", True),
        )
    )

    # Error handlers
    @app.errorhandler(404)
    def not_found(_err):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_err):
        logger.exception("Unhandled server error")
        return render_template("errors/500.html"), 500

    # Optional: initialize tables on startup only when explicitly requested.
    if os.getenv("INIT_DB_ON_STARTUP", "0") == "1":
        logger.info("INIT_DB_ON_STARTUP=1; initializing database schema")
        init_db()

    return app


# NOTE: Do not instantiate the Flask app at import time.
# Tests patch the DB engine/sessionmaker before calling create_app().
app: Flask | None = None


if __name__ == "__main__":
    app = create_app()
    get_logger(__name__).info("Starting Flask app")
    app.run(debug=True, use_reloader=False)
