import os

from flask import Flask, render_template

from api.blueprint import create_api_blueprint
from config import configure_logging
from db import Base, engine


def init_db() -> None:
    """Initialize DB schema.

    Kept out of default startup path to minimize app spin-up time.
    """

    Base.metadata.create_all(bind=engine)


def create_app() -> Flask:
    app = Flask(__name__)

    # Load config from file.
    app.config.from_pyfile("settings.py")

    # Configure logging
    configure_logging(app.logger, app.config.get("LOG_LEVEL", "INFO"))

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
        return render_template("errors/500.html"), 500

    # Optional: initialize tables on startup only when explicitly requested.
    if os.getenv("INIT_DB_ON_STARTUP", "0") == "1":
        init_db()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
