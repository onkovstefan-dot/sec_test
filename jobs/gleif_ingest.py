from __future__ import annotations

"""Initial GLEIF ingestion job (skeleton).

This session only establishes the base pattern + data source registry.
Full GLEIF LEI ingestion will be implemented in later sessions.
"""

from support.source_ingest_base import IngestRunResult, SourceIngestBase


class GLEIFIngestJob(SourceIngestBase):
    source_name = "gleif"

    def run(self) -> IngestRunResult:
        # Placeholder: no ingestion performed yet.
        return IngestRunResult(processed_files=0, inserted_records=0)


def main() -> None:
    job = GLEIFIngestJob()
    job.run()


if __name__ == "__main__":
    main()
