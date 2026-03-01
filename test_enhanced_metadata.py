#!/usr/bin/env python3
"""Test the enhanced metadata extraction with real submissions files."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.populate_daily_values import extract_metadata_from_submissions


def test_file(filepath):
    """Test metadata extraction from a single file."""
    with open(filepath, "r") as f:
        data = json.load(f)

    metadata = extract_metadata_from_submissions(data)

    print(f"\n{'=' * 80}")
    print(f"File: {os.path.basename(filepath)}")
    print(f"Entity: {data.get('name', 'N/A')}")
    print(f"{'=' * 80}")

    # Group fields by category
    categories = {
        "Company ID": ["company_name", "ein", "entity_type"],
        "Industry": ["sic", "sic_description"],
        "Incorporation": [
            "state_of_incorporation",
            "state_of_incorporation_description",
            "fiscal_year_end",
            "filer_category",
        ],
        "Contact": [
            "website",
            "investor_website",
            "phone",
            "entity_description",
            "owner_organization",
        ],
        "Regulatory": [
            "lei",
            "sec_flags",
            "has_insider_transactions_as_owner",
            "has_insider_transactions_as_issuer",
        ],
        "Trading": ["tickers", "exchanges"],
        "Business Address": [
            "business_street1",
            "business_street2",
            "business_city",
            "business_state",
            "business_zipcode",
            "business_country",
        ],
        "Mailing Address": [
            "mailing_street1",
            "mailing_street2",
            "mailing_city",
            "mailing_state",
            "mailing_zipcode",
            "mailing_country",
        ],
        "History": ["former_names"],
    }

    total_populated = 0
    for category, fields in categories.items():
        populated = [f for f in fields if f in metadata and metadata[f]]
        if populated:
            print(f"\n{category} ({len(populated)}/{len(fields)} fields):")
            for field in populated:
                value = metadata[field]
                # Truncate long values
                if isinstance(value, str) and len(value) > 60:
                    value = value[:57] + "..."
                print(f"  {field:40s} = {value}")
            total_populated += len(populated)

    print(f"\n{'=' * 80}")
    print(f"Total fields populated: {total_populated}/33")
    print(f"{'=' * 80}")

    return total_populated


def main():
    """Test metadata extraction on multiple submissions files."""
    submissions_dir = "raw_data/submissions"

    if not os.path.exists(submissions_dir):
        print(f"Directory not found: {submissions_dir}")
        return

    # Test files with different characteristics
    test_files = [
        "CIK0001767513.json",  # Has former names
        "CIK0001538927.json",  # Operating company with full data
        "CIK0001708885.json",  # Foreign entity (Cayman Islands)
        "CIK0001368016.json",  # Individual (other type)
    ]

    total_counts = []

    for filename in test_files:
        filepath = os.path.join(submissions_dir, filename)
        if os.path.exists(filepath):
            count = test_file(filepath)
            total_counts.append(count)
        else:
            print(f"\nFile not found: {filename}")

    if total_counts:
        print(f"\n\n{'=' * 80}")
        print("SUMMARY")
        print(f"{'=' * 80}")
        print(f"Average fields populated: {sum(total_counts)/len(total_counts):.1f}/33")
        print(f"Min: {min(total_counts)}, Max: {max(total_counts)}")
        print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
