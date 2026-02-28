import logging
import os


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


class Config:
    """Base configuration loaded from environment variables."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-not-secret")

    # Feature flags
    ENABLE_ADMIN: bool = _env_bool("ENABLE_ADMIN", True)
    ENABLE_DB_CHECK: bool = _env_bool("ENABLE_DB_CHECK", True)

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()


def configure_logging(app_logger: logging.Logger, level_name: str) -> None:
    """Configure application logging in a simple, predictable way."""

    level = getattr(logging, level_name, logging.INFO)

    # Avoid duplicate handlers (e.g., in tests or reload scenarios)
    if app_logger.handlers:
        app_logger.setLevel(level)
        return

    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)

    app_logger.addHandler(handler)
    app_logger.setLevel(level)
