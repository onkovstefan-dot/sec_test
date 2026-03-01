#!/usr/bin/env python3
"""End-to-end test for entity metadata extraction and storage."""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from models.entities import Entity
from models.entity_metadata import EntityMetadata
from utils.populate_daily_values import (
    extract_entity_identity,
    extract_metadata_from_submissions,
    get_or_create_entity,
)


def test_metadata_extraction_and_storage():
    """Test that metadata is correctly extracted and stored."""

    # Create a temporary in-memory database for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Monkey-patch the populate_daily_values session
    import utils.populate_daily_values as pdv

    original_session = pdv.session
    pdv.session = session

    try:
        # Test data mimicking a submissions file
        test_data = {
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

        print("=" * 80)
        print("Testing Entity Metadata Extraction and Storage")
        print("=" * 80)

        # Step 1: Extract metadata
        print("\n1. Extracting metadata from test data...")
        metadata = extract_metadata_from_submissions(test_data)
        print(f"   ✓ Extracted {len(metadata)} fields")

        # Step 2: Extract entity identity
        print("\n2. Extracting entity identity...")
        cik, company_name, extracted_metadata = extract_entity_identity(
            test_data, "CIK0001538927.json"
        )
        print(f"   ✓ CIK: {cik}")
        print(f"   ✓ Company Name: {company_name}")
        print(f"   ✓ Metadata fields: {len(extracted_metadata)}")

        # Step 3: Create entity with metadata
        print("\n3. Creating entity with metadata...")
        entity = get_or_create_entity(cik, company_name, extracted_metadata)
        session.flush()
        print(f"   ✓ Entity created with ID: {entity.id}")

        # Step 4: Verify metadata was stored
        print("\n4. Verifying metadata storage...")
        meta = session.query(EntityMetadata).filter_by(entity_id=entity.id).first()

        if not meta:
            print("   ✗ ERROR: Metadata record not found!")
            return False

        print(f"   ✓ Metadata record found for entity_id: {meta.entity_id}")

        # Check specific fields
        checks = [
            ("company_name", "Forma Therapeutics Holdings, Inc."),
            ("sic", "2836"),
            ("sic_description", "Biological Products, (No Diagnostic Substances)"),
            ("state_of_incorporation", "DE"),
            ("fiscal_year_end", "1231"),
            ("filer_category", "Large accelerated filer"),
            ("entity_type", "operating"),
            ("phone", "617-679-1970"),
            ("ein", "371657129"),
            ("website", "https://example.com"),
            ("business_city", "WATERTOWN"),
            ("business_state", "MA"),
            ("business_street1", "300 NORTH BEACON STREET"),
            ("business_zipcode", "02472"),
        ]

        print("\n5. Verifying individual fields:")
        passed = 0
        failed = 0
        for field_name, expected_value in checks:
            actual_value = getattr(meta, field_name, None)
            if actual_value == expected_value:
                print(f"   ✓ {field_name:25s} = {actual_value}")
                passed += 1
            else:
                print(
                    f"   ✗ {field_name:25s} = {actual_value} (expected: {expected_value})"
                )
                failed += 1

        # Check JSON fields
        print("\n6. Verifying JSON fields:")
        tickers = meta.tickers
        exchanges = meta.exchanges
        if tickers:
            tickers_list = json.loads(tickers)
            print(f"   ✓ tickers = {tickers_list}")
            passed += 1
        else:
            print(f"   ✗ tickers field is empty")
            failed += 1

        if exchanges:
            exchanges_list = json.loads(exchanges)
            print(f"   ✓ exchanges = {exchanges_list}")
            passed += 1
        else:
            print(f"   ✗ exchanges field is empty")
            failed += 1

        # Test updating with no-op (should not overwrite existing)
        print("\n7. Testing idempotent updates...")
        entity2 = get_or_create_entity(cik, "Different Name", {"sic": "9999"})
        session.flush()
        meta2 = session.query(EntityMetadata).filter_by(entity_id=entity2.id).first()
        if (
            meta2.company_name == "Forma Therapeutics Holdings, Inc."
            and meta2.sic == "2836"
        ):
            print("   ✓ Existing values preserved (no overwrite)")
            passed += 1
        else:
            print("   ✗ Existing values were overwritten!")
            failed += 1

        # Summary
        print("\n" + "=" * 80)
        print(f"Test Summary: {passed} passed, {failed} failed")
        print("=" * 80)

        return failed == 0

    finally:
        # Restore original session
        pdv.session = original_session
        session.close()
        engine.dispose()


if __name__ == "__main__":
    success = test_metadata_extraction_and_storage()
    sys.exit(0 if success else 1)
