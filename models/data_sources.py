from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text

from db import Base
from utils.time_utils import utcnow_sa_default


class DataSource(Base):
    """Registry of external data sources.

    This table is intended to be small and relatively static. It provides a
    canonical set of source names that other parts of the system can reference
    (e.g. `value_names.source`, `daily_values.source`, `file_processing.source`).
    """

    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Short canonical name used across the system (e.g. 'sec', 'gleif').
    name = Column(String, unique=True, nullable=False)

    # Human-readable label (optional).
    display_name = Column(String, nullable=True)

    # Free-form notes (optional): URL, licensing notes, etc.
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utcnow_sa_default)
