"""App settings.

Flask loads this module on startup via ``app.config.from_pyfile(...)``.

For now this file uses a simple dict-like structure (no environment variables).
"""

# Single source of truth for app configuration.
SETTINGS: dict[str, object] = {
    # Flask
    "SECRET_KEY": "dev-not-secret",
    # Feature flags
    "ENABLE_DB_CHECK": True,
    # Logging
    "LOG_LEVEL": "INFO",
    # SEC EDGAR
    # SEC requires a descriptive User-Agent that includes contact info.
    # Example: "InvestorGuide your.name@domain.com"
    "SEC_USER_AGENT": "InvestorGuide (set SETTINGS['SEC_USER_AGENT'] to your@email.com)",
}

# Optional convenience exports (mirrors earlier style).
SECRET_KEY = SETTINGS["SECRET_KEY"]
ENABLE_DB_CHECK = SETTINGS["ENABLE_DB_CHECK"]
LOG_LEVEL = SETTINGS["LOG_LEVEL"]
SEC_USER_AGENT = SETTINGS["SEC_USER_AGENT"]
