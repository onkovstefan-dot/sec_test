"""SQLAlchemy models package.

Important: This project uses a single declarative Base defined in `db.py`.
Import `Base` from this package in all model modules.

Example:

    Base.metadata.create_all(...)

This keeps `Base.metadata` consistent across the app.
"""

from db import Base  # re-export a single shared Base
