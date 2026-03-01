#!/usr/bin/env python3
"""
Backfill missing document_url in sec_filings table.

For filings that have index_url but missing document_url, construct the document_url
based on SEC EDGAR patterns:
  https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{accession}.txt

This allows previously failed filings to be retried with --retry-failed.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from db import SessionLocal
from models.sec_filings import SecFiling
from logging_utils import get_logger
from sqlalchemy import or_

logger = get_logger(__name__)


def _infer_cik_from_url(url: str | None) -> str | None:
    """Extract CIK from SEC archive URL."""
    if not url:
        return None
    s = str(url)
    marker = "/Archives/edgar/data/"
    if marker not in s:
        return None
    tail = s.split(marker, 1)[1]
    parts = tail.split("/")
    if parts and parts[0].isdigit():
        return parts[0]
    return None


def _normalize_accession(accession: str) -> str:
    """Normalize accession number by removing dashes."""
    return str(accession).strip().replace("-", "")


def backfill_document_urls(*, dry_run: bool = False) -> dict[str, int]:
    """
    Backfill missing document_url fields.

    Args:
        dry_run: If True, only report what would be changed without updating.

    Returns:
        Summary counts.
    """
    with SessionLocal() as session:
        # Find filings with missing document_url but have index_url or full_text_url
        q = (
            session.query(SecFiling)
            .filter(or_(SecFiling.document_url == None, SecFiling.document_url == ""))
            .filter(or_(SecFiling.index_url != None, SecFiling.full_text_url != None))
        )

        filings = q.all()

        if not filings:
            logger.info("No filings found with missing document_url to backfill.")
            return {"found": 0, "updated": 0, "skipped": 0}

        logger.info("Found %s filings with missing document_url", len(filings))

        updated = 0
        skipped = 0

        for filing in filings:
            # Try to infer CIK from available URLs
            cik = None
            for url in (filing.index_url, filing.full_text_url):
                cik = _infer_cik_from_url(url)
                if cik:
                    break

            if not cik:
                logger.warning(
                    "Cannot infer CIK | filing_id=%s accession=%s",
                    filing.id,
                    filing.accession_number,
                )
                skipped += 1
                continue

            if not filing.accession_number:
                logger.warning(
                    "Missing accession_number | filing_id=%s",
                    filing.id,
                )
                skipped += 1
                continue

            # Construct document_url: typically the primary .txt file
            accession_normalized = _normalize_accession(filing.accession_number)
            document_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                f"{accession_normalized}/{filing.accession_number}.txt"
            )

            if dry_run:
                logger.info(
                    "Would update | filing_id=%s accession=%s form_type=%s document_url=%s",
                    filing.id,
                    filing.accession_number,
                    filing.form_type,
                    document_url,
                )
            else:
                filing.document_url = document_url
                logger.info(
                    "Updated | filing_id=%s accession=%s form_type=%s document_url=%s",
                    filing.id,
                    filing.accession_number,
                    filing.form_type,
                    document_url,
                )

            updated += 1

        if not dry_run:
            session.commit()
            logger.info("Committed %s document_url updates", updated)

        return {"found": len(filings), "updated": updated, "skipped": skipped}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill missing document_url in sec_filings"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without updating the database",
    )
    args = parser.parse_args()

    logger.info(
        "Starting document_url backfill | dry_run=%s",
        args.dry_run,
    )

    summary = backfill_document_urls(dry_run=args.dry_run)

    logger.info(
        "Backfill complete | found=%s updated=%s skipped=%s",
        summary["found"],
        summary["updated"],
        summary["skipped"],
    )

    print(f"\nBackfill complete:")
    print(f"  Found: {summary['found']}")
    print(f"  Updated: {summary['updated']}")
    print(f"  Skipped: {summary['skipped']}")

    if args.dry_run:
        print("\n(Dry run - no changes made)")


if __name__ == "__main__":
    main()
