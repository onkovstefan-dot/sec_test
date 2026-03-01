from __future__ import annotations

from models.entities import Entity
from models.entity_identifiers import EntityIdentifier
from models.sec_filings import SecFiling
from pytests.common import create_empty_sqlite_db


def test_sec_rss_poller_upserts_pending_and_skips_unknown_cik(tmp_path, monkeypatch):
    session, _engine = create_empty_sqlite_db(tmp_path / "rss.sqlite")

    import jobs.sec_rss_poller as poller

    # Seed one known entity with sec_cik identifier.
    e = Entity(cik="0000320193")
    session.add(e)
    session.flush()
    session.add(EntityIdentifier(entity_id=e.id, scheme="sec_cik", value="0000320193"))
    session.commit()

    atom = """<?xml version='1.0' encoding='UTF-8'?>
        <feed xmlns='http://www.w3.org/2005/Atom'>
          <entry>
            <title>8-K - Apple Inc (CIK=0000320193) (0000320193-24-000001)</title>
            <summary>something</summary>
            <link href='https://www.sec.gov/Archives/edgar/data/320193/000032019324000001/0000320193-24-000001-index.htm'/>
          </entry>
          <entry>
            <title>10-K - Unknown Co (CIK=0000000001) (0000000001-24-000001)</title>
            <summary>something</summary>
            <link href='https://www.sec.gov/Archives/edgar/data/1/000000000124000001/0000000001-24-000001-index.htm'/>
          </entry>
        </feed>
        """.encode(
        "utf-8"
    )

    monkeypatch.setattr(poller, "fetch_rss_feed", lambda url=None: atom)

    summary = poller.run_poll(session=session, url="http://example.test/atom", limit=50)
    assert summary["inserted"] == 1
    assert summary["unknown_cik"] == 1

    f = session.query(SecFiling).filter_by(entity_id=e.id).first()
    assert f is not None
    assert f.accession_number == "000032019324000001"
    assert f.form_type == "8-K"
    assert f.fetch_status == "pending"
    assert f.source == "sec_rss"

    # Idempotent: second run inserts nothing
    summary2 = poller.run_poll(
        session=session, url="http://example.test/atom", limit=50
    )
    assert summary2["inserted"] == 0
