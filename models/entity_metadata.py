from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String

from models import Base


class EntityMetadata(Base):
    """Additional metadata for an entity (1:1 with entities).

    Companyfacts JSON currently only provides `entityName` at the top level.
    This table is designed to grow as we ingest metadata from other SEC datasets
    (e.g. submissions, tickers, exchange mappings, etc.).
    """

    __tablename__ = "entity_metadata"
    __table_args__ = {"extend_existing": True}

    entity_id = Column(
        Integer,
        ForeignKey("entities.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    # Optional metadata
    company_name = Column(String, nullable=True)
    country = Column(String, nullable=True)
    sector = Column(String, nullable=True)
