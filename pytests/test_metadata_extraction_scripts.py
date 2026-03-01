from __future__ import annotations

import json

from utils.populate_daily_values import extract_metadata_from_submissions


def test_extract_metadata_from_submissions_smoke():
    """Basic sanity check for the metadata extractor.

    Replaces the old root-level ad-hoc scripts with a deterministic unit test.
    """

    sample = {
        "cik": "0001538927",
        "name": "Forma Therapeutics Holdings, Inc.",
        "sic": "2836",
        "sicDescription": "Biological Products, (No Diagnostic Substances)",
        "stateOfIncorporation": "DE",
        "fiscalYearEnd": "1231",
        "category": "Large accelerated filer",
        "entityType": "operating",
        "phone": "617-679-1970",
        "ein": "371657129",
        "website": "https://example.com",
        "tickers": ["FMTX"],
        "exchanges": ["NASDAQ"],
        "addresses": {
            "business": {
                "street1": "300 NORTH BEACON STREET",
                "street2": "SUITE 501",
                "city": "WATERTOWN",
                "stateOrCountry": "MA",
                "zipCode": "02472",
            }
        },
    }

    md = extract_metadata_from_submissions(sample)
    assert isinstance(md, dict)

    # A few stable fields we expect to be extracted.
    assert md.get("company_name") == "Forma Therapeutics Holdings, Inc."
    assert md.get("sic") == "2836"
    assert (
        md.get("sic_description") == "Biological Products, (No Diagnostic Substances)"
    )
    assert md.get("state_of_incorporation") == "DE"

    # Those scripts used to print JSON-ish fields; ensure they're serialized.
    if "tickers" in md and md["tickers"]:
        json.loads(md["tickers"])  # should be valid JSON
    if "exchanges" in md and md["exchanges"]:
        json.loads(md["exchanges"])
