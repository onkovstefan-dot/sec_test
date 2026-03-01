from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from db import Base


class SecFilingDocument(Base):
    __tablename__ = "sec_filing_documents"
    __table_args__ = (
        UniqueConstraint(
            "filing_id",
            "doc_type",
            name="uq_sec_filing_documents_filing_doc_type",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    filing_id = Column(
        Integer,
        ForeignKey("sec_filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    doc_type = Column(String, nullable=False)  # e.g. 'primary', 'full_text', 'index'

    filename = Column(String, nullable=True)
    local_path = Column(String, nullable=True)
    url = Column(String, nullable=True)

    size_bytes = Column(Integer, nullable=True)

    fetched_at = Column(DateTime, nullable=True)
    fetch_status = Column(String, nullable=False, default="pending")
