import json


def process_companyfacts_json(file_path):
    """
    Process a SEC companyfacts JSON file and extract relevant facts data.
    Returns a list of dicts with flattened fact data for each unit/value.
    """
    with open(file_path, "r") as f:
        data = json.load(f)
    cik = data.get("cik")
    facts = data.get("facts", {})
    results = []
    for taxonomy, taxonomy_data in facts.items():
        for tag, tag_data in taxonomy_data.items():
            units = tag_data.get("units", {})
            for unit, values in units.items():
                for value in values:
                    entry = {
                        "cik": cik,
                        "taxonomy": taxonomy,
                        "tag": tag,
                        "unit": unit,
                        "value": value.get("val"),
                        "start": value.get("start"),
                        "end": value.get("end"),
                        "accn": value.get("accn"),
                        "fy": value.get("fy"),
                        "fp": value.get("fp"),
                        "form": value.get("form"),
                        "filed": value.get("filed"),
                        "frame": value.get("frame"),
                    }
                    results.append(entry)
    return results


# Data processing logic
