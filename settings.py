"""App settings.

Flask loads this module on startup via ``app.config.from_pyfile(...)``.

For now this file uses a simple dict-like structure (no environment variables).
"""

# Single source of truth for app configuration.
SETTINGS: dict[str, object] = {
    # Flask
    "SECRET_KEY": "dev-not-secret",
    # Feature flags
    "ENABLE_ADMIN": True,
    "ENABLE_DB_CHECK": True,
    # Logging
    "LOG_LEVEL": "INFO",
}

# Optional convenience exports (mirrors earlier style).
SECRET_KEY = SETTINGS["SECRET_KEY"]
ENABLE_ADMIN = SETTINGS["ENABLE_ADMIN"]
ENABLE_DB_CHECK = SETTINGS["ENABLE_DB_CHECK"]
LOG_LEVEL = SETTINGS["LOG_LEVEL"]
