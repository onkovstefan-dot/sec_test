from __future__ import annotations

from datetime import date

import pytest

from app import create_app
from models.entities import Entity
from models.sec_filings import SecFiling
from pytests.common import create_empty_sqlite_db, patch_app_db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    session, engine = create_empty_sqlite_db(tmp_path / "test.sqlite")
    patch_app_db(monkeypatch, engine)

    # Seed one entity + one local filing.
    e = Entity(cik="0000000001")
    session.add(e)
    session.flush()

    f = SecFiling(
        entity_id=e.id,
        accession_number="000000000120000001",
        form_type="10-K",
        filing_date=date(2024, 1, 5),
        index_url="https://www.sec.gov/Archives/edgar/data/1/000000000120000001/0000000001-20-000001-index.htm",
        document_url="https://www.sec.gov/Archives/edgar/data/1/000000000120000001/primary.htm",
        full_text_url="https://www.sec.gov/Archives/edgar/data/1/000000000120000001/0000000001-20-000001.txt",
        fetch_status="pending",
        source="sec_submissions_local",
    )
    session.add(f)
    session.commit()
    session.close()

    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c

    engine.dispose()


def test_filings_search_prefers_local_results(client, monkeypatch):
    # If local results exist, EFTS should not be called.
    import api.api_v1.filings as filings_mod

    def _boom(**kwargs):  # pragma: no cover
        raise AssertionError("EFTS should not be called when local results exist")

    monkeypatch.setattr(filings_mod, "fetch_efts_search", _boom, raising=True)

    res = client.get("/api/v1/filings/search?form_type=10-K&limit=10")
    assert res.status_code == 200

    payload = res.get_json()
    assert payload["source"] == "local"
    assert payload["count"] == 1
    assert payload["results"][0]["accession_number"] == "000000000120000001"


def test_filings_search_falls_back_to_efts_when_no_local_hits(client, monkeypatch):
    import api.api_v1.filings as filings_mod

    # Choose a query that won't match local filtering; also filter by form type not present.
    fake_hits = [
        {
            "accession_number": "000012345620000001",
            "cik": "123456",
            "form_type": "S-1",
            "filed_at": "2024-02-01",
            "company_name": "X",
            "link": "https://example.com",
            "snippet": "hello",
        }
    ]

    class _Hit:
        def __init__(self, d):
            self.accession_number = d["accession_number"]
            self.cik = d["cik"]
            self.form_type = d["form_type"]
            self.filed_at = d["filed_at"]
            self.company_name = d["company_name"]
            self.link = d["link"]
            self.snippet = d["snippet"]

    def _fake_fetch(**kwargs):
        assert kwargs["q"] == "test"
        return [_Hit(fake_hits[0])]

    monkeypatch.setattr(filings_mod, "fetch_efts_search", _fake_fetch, raising=True)

    res = client.get("/api/v1/filings/search?q=test&form_type=S-1&limit=5")
    assert res.status_code == 200

    payload = res.get_json()
    assert payload["source"] == "efts"
    assert payload["count"] == 1
    assert payload["results"][0]["cik"] == "123456"
    assert payload["results"][0]["form_type"] == "S-1"
