from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint

from db import Base


class SecTicker(Base):
    __tablename__ = "sec_tickers"
    __table_args__ = (
        UniqueConstraint("ticker", "exchange", name="uq_sec_tickers_ticker_exchange"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    entity_id = Column(
        Integer,
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    ticker = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=True, index=True)

    # SQLite-friendly boolean (0/1)
    is_active = Column(Integer, nullable=False, default=1)

    source = Column(String, nullable=False, default="sec_submissions_local")
