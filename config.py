import logging
import os

from logging_utils import configure_app_logging


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


def configure_logging(_app_logger: logging.Logger, level_name: str) -> None:
    """Backward-compatible shim.

    Prefer importing and calling `configure_app_logging` from `logging_utils`.
    """

    configure_app_logging(level_name)
