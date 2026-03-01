from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import db


@dataclass(frozen=True)
class IngestRunResult:
    processed_files: int
    inserted_records: int


class SourceIngestBase(abc.ABC):
    """Reusable base class for source ingestion jobs.

    Subclasses should implement:
    - `source_name`: canonical identifier (must match `data_sources.name`).
    - `run()`: perform ingestion and return counts.

    This is intentionally light-weight: the existing pipeline uses separate
    mechanisms (e.g. `file_processing`) for idempotence. This class gives a
    consistent interface for future sources and jobs.
    """

    source_name: str

    def __init__(
        self,
        *,
        raw_data_dir: Path | str | None = None,
        session_factory: Any = None,
    ) -> None:
        self.raw_data_dir = Path(raw_data_dir) if raw_data_dir else None
        self.session_factory = session_factory or db.SessionLocal

    @abc.abstractmethod
    def run(self) -> IngestRunResult:  # pragma: no cover
        raise NotImplementedError
