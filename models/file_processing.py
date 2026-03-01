from models import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint

from utils.time_utils import utcnow_sa_default


class FileProcessing(Base):
    """Tracks per-file processing progress for incremental runs.

    Uniqueness is enforced by (entity_id, source_file).

    - entity_id: links to entities.id (CIK)
    - source_file: stable identifier for an ingested JSON file (see utils.populate_daily_values)
    - source: provenance tag describing where the file came from (e.g. 'local', 'sec_api')
    - record_count: best-effort count of logical records processed from this file
    - processed_at: UTC timestamp when the file was successfully processed/committed
    """

    __tablename__ = "file_processing"
    __table_args__ = (
        UniqueConstraint(
            "entity_id",
            "source_file",
            name="uq_file_processing_entity_source_file",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    source_file = Column(String, nullable=False)

    # New tracking fields (Session 7)
    source = Column(String, nullable=False, default="local")
    record_count = Column(Integer, nullable=True)

    processed_at = Column(DateTime, nullable=False, default=utcnow_sa_default)
