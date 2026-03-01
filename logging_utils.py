"""Application logging utilities.

Goals:
- Single, shared app logger used everywhere
- Logs written to per-module files under ./logs/
- UTC timestamp at start of each log line
- Daily log rotation

Implementation notes:
- Uses `TimedRotatingFileHandler` with `when='midnight'` and `utc=True`.
- Also attaches a console handler (stderr) for local development.
- Call `get_logger(__name__)` from any module to get a child logger.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler


class _UTCFormatter(logging.Formatter):
    """Formatter that forces UTC timestamps."""

    converter = staticmethod(__import__("time").gmtime)


_APP_LOGGER_NAME = "sec_test"


def _logs_dir() -> str:
    # project_root/logs
    here = os.path.dirname(__file__)
    return os.path.join(here, "logs")


def _sanitize_filename(name: str) -> str:
    # Convert e.g. "api.routes" -> "api_routes"
    name = (name or "app").strip() or "app"
    return "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "_" for ch in name)


def configure_app_logging(level_name: str = "INFO") -> logging.Logger:
    """Configure and return the root application logger.

    Safe to call multiple times.
    """

    level = getattr(logging, (level_name or "INFO").upper(), logging.INFO)
    app_logger = logging.getLogger(_APP_LOGGER_NAME)
    app_logger.setLevel(level)

    # Ensure the logs directory exists.
    os.makedirs(_logs_dir(), exist_ok=True)

    # Avoid duplicate handlers.
    if getattr(app_logger, "_configured", False):
        return app_logger

    fmt = _UTCFormatter(
        fmt="%(asctime)sZ %(levelname)s pid=%(process)d %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Console handler
    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(fmt)

    # Default file handler for top-level/root logs.
    root_log_path = os.path.join(_logs_dir(), "app.log")
    fh = TimedRotatingFileHandler(
        root_log_path,
        when="midnight",
        interval=1,
        backupCount=14,
        utc=True,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(fmt)

    app_logger.addHandler(sh)
    app_logger.addHandler(fh)

    # Do not propagate to the global root logger (prevents double logging).
    app_logger.propagate = False

    # Mark configured.
    app_logger._configured = True  # type: ignore[attr-defined]
    return app_logger


def get_logger(module_name: str | None = None) -> logging.Logger:
    """Get a module-specific logger that writes to its own log file.

    Example:
        logger = get_logger(__name__)
    """

    base = configure_app_logging(os.getenv("LOG_LEVEL", "INFO"))

    child_name = module_name or "app"
    logger = logging.getLogger(f"{_APP_LOGGER_NAME}.{child_name}")

    # Ensure the child has a per-file handler (only once).
    if not getattr(logger, "_file_configured", False):
        level = base.level
        logger.setLevel(level)
        logger.propagate = False

        fmt = _UTCFormatter(
            fmt="%(asctime)sZ %(levelname)s pid=%(process)d %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

        file_name = _sanitize_filename(child_name) + ".log"
        log_path = os.path.join(_logs_dir(), file_name)

        fh = TimedRotatingFileHandler(
            log_path,
            when="midnight",
            interval=1,
            backupCount=14,
            utc=True,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(fmt)

        logger.addHandler(fh)
        logger._file_configured = True  # type: ignore[attr-defined]

    return logger
