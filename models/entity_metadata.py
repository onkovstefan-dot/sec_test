from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, DateTime

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

    # Optional metadata from companyfacts / submissions
    company_name = Column(String, nullable=True)

    # SIC (Standard Industrial Classification)
    sic = Column(String, nullable=True)
    sic_description = Column(String, nullable=True)

    # Incorporation and fiscal info
    state_of_incorporation = Column(String, nullable=True)
    fiscal_year_end = Column(String, nullable=True)

    # Filer category and entity type
    filer_category = Column(String, nullable=True)
    entity_type = Column(String, nullable=True)

    # Contact information
    website = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    ein = Column(String, nullable=True)

    # Additional entity info
    lei = Column(String, nullable=True)  # Legal Entity Identifier
    investor_website = Column(String, nullable=True)
    entity_description = Column(String, nullable=True)
    owner_organization = Column(String, nullable=True)
    state_of_incorporation_description = Column(String, nullable=True)

    # Regulatory flags
    sec_flags = Column(String, nullable=True)
    has_insider_transactions_as_owner = Column(Integer, nullable=True)
    has_insider_transactions_as_issuer = Column(Integer, nullable=True)

    # Trading info
    tickers = Column(String, nullable=True)  # JSON string or comma-separated
    exchanges = Column(String, nullable=True)  # JSON string or comma-separated

    # Business address
    business_street1 = Column(String, nullable=True)
    business_street2 = Column(String, nullable=True)
    business_city = Column(String, nullable=True)
    business_state = Column(String, nullable=True)
    business_zipcode = Column(String, nullable=True)
    business_country = Column(String, nullable=True)

    # Mailing address (may differ from business address)
    mailing_street1 = Column(String, nullable=True)
    mailing_street2 = Column(String, nullable=True)
    mailing_city = Column(String, nullable=True)
    mailing_state = Column(String, nullable=True)
    mailing_zipcode = Column(String, nullable=True)
    mailing_country = Column(String, nullable=True)

    # Former names (stored as JSON array)
    former_names = Column(String, nullable=True)  # JSON array of {name, from, to}

    # Multi-source bookkeeping
    data_sources = Column(String, nullable=True)  # JSON or comma-separated source names
    last_sec_sync_at = Column(DateTime, nullable=True)

    # Deprecated fields (kept for backwards compatibility)
    country = Column(String, nullable=True)
    sector = Column(String, nullable=True)
