"""Legacy loader for a staging table.

This file previously created/populated the `submissions_flat` table.
That table/model has been removed in favor of the core 4-table schema:
- entities
- dates
- value_names
- daily_values

Kept as a placeholder to avoid recreating dropped tables by accident.
"""

raise SystemExit(
    "load_to_db.py is deprecated and intentionally disabled. "
    "Use utils/populate_daily_values.py instead."
)
