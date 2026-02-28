"""Deprecated legacy loader.

This file previously created/populated a staging table.
Kept here as a placeholder to avoid recreating dropped tables by accident.

Not used by the Flask app at runtime.
"""

raise SystemExit(
    "load_to_db.py is deprecated and intentionally disabled. "
    "Use utils/populate_daily_values.py instead."
)
