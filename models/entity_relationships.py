from __future__ import annotations

from sqlalchemy import (
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from db import Base


class EntityRelationship(Base):
    """Entity-to-entity relationship edge.

    This table is intentionally minimal:
    - It references entities by integer PK (`entities.id`) only.
    - It allows multiple relationship types between the same pair.
    - It encodes a uniqueness constraint to keep ingestion idempotent.
    """

    __tablename__ = "entity_relationships"
    __table_args__ = (
        UniqueConstraint(
            "parent_entity_id",
            "child_entity_id",
            "relationship_type",
            name="uq_entity_relationships_parent_child_type",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    parent_entity_id = Column(
        Integer,
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    child_entity_id = Column(
        Integer,
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    relationship_type = Column(String, nullable=False)

    ownership_pct = Column(Float, nullable=True)
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)
    source = Column(String, nullable=True)
