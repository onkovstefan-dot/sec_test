from models import Base
from sqlalchemy import Column, Integer, String


class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Canonical internal stable identifier (not used as FK in other tables).
    # Stored as string for SQLite portability.
    canonical_uuid = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
        default=lambda: __import__("uuid").uuid4().hex,
    )

    # Legacy SEC field.
    # IMPORTANT: For global/non-US coverage we cannot rely on CIK uniqueness or presence.
    # Strict matching should use `entity_identifiers (scheme,value)`.
    cik = Column(String, nullable=True)
