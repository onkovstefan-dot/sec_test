from flask import Flask
from api.routes import api_bp
import os

from db import engine, Base


def init_db() -> None:
    """Initialize DB schema.

    Kept out of default startup path to minimize app spin-up time.
    """
    Base.metadata.create_all(bind=engine)


app = Flask(__name__)
app.register_blueprint(api_bp)

# Optional: initialize tables on startup only when explicitly requested.
if os.getenv("INIT_DB_ON_STARTUP", "0") == "1":
    init_db()

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
