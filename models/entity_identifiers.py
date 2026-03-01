from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from models import Base
from utils.time_utils import utcnow_sa_default


class EntityIdentifier(Base):
    """External identifier for an Entity.

    Design goals:
    - Keep `entities.id` as the primary FK used by large fact tables.
    - Support strict/exact matching across multiple sources via typed identifiers.

    Uniqueness:
    - `(scheme, value)` is unique (case-normalized by ingestion code).
    - `entity_id` is not unique; one entity can have many identifiers.

    Examples:
    - scheme='sec_cik', value='0000320193'
    - scheme='gleif_lei', value='5493001KJTIIGC8Y1R12'
    - scheme='gb_companies_house', value='01234567'
    - scheme='fr_siren', value='552100554'
    """

    __tablename__ = "entity_identifiers"
    __table_args__ = (
        UniqueConstraint("scheme", "value", name="uq_entity_identifiers_scheme_value"),
        # entity_id is already indexed via Column(index=True)
        Index("ix_entity_identifiers_scheme", "scheme"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    entity_id = Column(
        Integer,
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identifier namespace/type.
    scheme = Column(String, nullable=False)

    # Identifier value. Store normalized (trimmed; upper where appropriate; digits for CIK, etc.).
    value = Column(String, nullable=False)

    # Optional context.
    country = Column(String, nullable=True)
    issuer = Column(String, nullable=True)  # e.g. 'sec', 'gleif', 'companies_house'

    # Auditability.
    confidence = Column(String, nullable=False, default="authoritative")
    added_at = Column(DateTime, nullable=False, default=utcnow_sa_default)
    last_seen_at = Column(DateTime, nullable=True)

    entity = relationship("Entity")
