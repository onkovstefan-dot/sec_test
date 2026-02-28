"""SQLAlchemy models package.

Important: This project uses a single declarative Base defined in `db.py`.
Import `Base` from here in all model modules:

    from models import Base

This keeps `Base.metadata` consistent across the app.
"""

from db import Base  # re-export a single shared Base
