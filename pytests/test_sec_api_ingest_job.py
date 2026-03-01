from __future__ import annotations

from pathlib import Path

from models.entities import Entity
from models.sec_filings import SecFiling
from pytests.common import create_empty_sqlite_db


def test_sec_api_ingest_updates_status_and_writes_file(tmp_path, monkeypatch):
    session, _engine = create_empty_sqlite_db(tmp_path / "ingest.sqlite")

    # Import after DB is ready.
    import jobs.sec_api_ingest as job

    # Redirect raw_data/forms output into tmp_path.
    monkeypatch.setattr(job, "RAW_DATA_DIR", Path(tmp_path) / "raw_data", raising=False)
    monkeypatch.setattr(
        job, "FORMS_DIR", Path(tmp_path) / "raw_data" / "forms", raising=False
    )

    # Create entity + filing row.
    e = Entity(cik="0000123456")
    session.add(e)
    session.flush()

    filing = SecFiling(
        entity_id=e.id,
        accession_number="000012345624000001",
        form_type="10-K",
        document_url="https://www.sec.gov/Archives/edgar/data/123456/000012345624000001/primary.htm",
        index_url="https://www.sec.gov/Archives/edgar/data/123456/000012345624000001/0000123456-24-000001-index.htm",
        fetch_status="pending",
    )
    session.add(filing)
    session.commit()

    # Mock network fetch.
    def _fake_fetch_filing_document(
        *, cik: str, accession_number: str, document_name: str, session=None
    ):
        assert cik == "123456"
        assert accession_number == "000012345624000001"
        assert document_name == "primary.htm"
        return b"<html>ok</html>"

    monkeypatch.setattr(job, "fetch_filing_document", _fake_fetch_filing_document)

    summary = job.run_ingest(session=session, form_types=["10-K"], limit=10, workers=1)
    assert summary["selected"] == 1
    assert summary["fetched"] == 1
    assert summary["failed"] == 0

    # DB updated.
    updated = session.query(SecFiling).filter_by(id=filing.id).first()
    assert updated is not None
    assert updated.fetch_status == "fetched"
    assert updated.fetched_at is not None

    # File written.
    out_path = (
        Path(tmp_path)
        / "raw_data"
        / "forms"
        / "123456"
        / "000012345624000001"
        / "primary.htm"
    )
    assert out_path.exists()
    assert out_path.read_bytes() == b"<html>ok</html>"
