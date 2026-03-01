#!/usr/bin/env python3
"""Test script to verify metadata extraction from submissions files."""

import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.populate_daily_values import extract_metadata_from_submissions

# Test with one of the submissions files we examined
test_file = "raw_data/submissions/CIK0001538927.json"

if not os.path.exists(test_file):
    # Try any submissions file
    submissions_dir = "raw_data/submissions"
    if os.path.exists(submissions_dir):
        files = [
            f
            for f in os.listdir(submissions_dir)
            if f.endswith(".json") and "submissions-001" not in f
        ]
        if files:
            test_file = os.path.join(submissions_dir, files[0])
            print(f"Using: {test_file}")

if os.path.exists(test_file):
    with open(test_file, "r") as f:
        data = json.load(f)

    metadata = extract_metadata_from_submissions(data)

    print("=" * 80)
    print(f"Metadata extracted from {os.path.basename(test_file)}:")
    print("=" * 80)
    for key, value in sorted(metadata.items()):
        # Truncate long values for display
        val_str = str(value)
        if len(val_str) > 60:
            val_str = val_str[:57] + "..."
        print(f"{key:25s} = {val_str}")
    print("=" * 80)
    print(f"Total fields extracted: {len(metadata)}")
else:
    print(f"No submissions files found")
