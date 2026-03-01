"""SQLAlchemy models package.

Important: This project uses a single declarative Base defined in `db.py`.
Import `Base` from this package in all model modules.

Example:

    Base.metadata.create_all(...)

This keeps `Base.metadata` consistent across the app.
"""

from db import Base  # re-export a single shared Base

# Import models so they are registered with SQLAlchemy metadata on startup.
# This makes `Base.metadata.create_all()` create all tables for a fresh DB.
#
# Keep imports local to this package to avoid circular dependencies in app code.
from models.entities import Entity  # noqa: F401
from models.entity_identifiers import EntityIdentifier  # noqa: F401
from models.entity_metadata import EntityMetadata  # noqa: F401
from models.dates import DateEntry  # noqa: F401
from models.units import Unit  # noqa: F401
from models.value_names import ValueName  # noqa: F401
from models.daily_values import DailyValue  # noqa: F401
from models.file_processing import FileProcessing  # noqa: F401
