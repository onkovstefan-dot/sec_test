from __future__ import annotations

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from db import Base


class SecFiling(Base):
    __tablename__ = "sec_filings"
    __table_args__ = (
        UniqueConstraint(
            "entity_id",
            "accession_number",
            name="uq_sec_filings_entity_accession",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    entity_id = Column(
        Integer,
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # normalized: dashes removed
    accession_number = Column(String, nullable=False, index=True)

    form_type = Column(String, nullable=False)

    filing_date = Column(Date, nullable=True)
    report_date = Column(Date, nullable=True)

    primary_document = Column(String, nullable=True)

    index_url = Column(String, nullable=True)
    document_url = Column(String, nullable=True)
    full_text_url = Column(String, nullable=True)

    fetched_at = Column(DateTime, nullable=True)
    fetch_status = Column(String, nullable=False, default="pending")

    source = Column(String, nullable=False, default="sec_submissions_local")
