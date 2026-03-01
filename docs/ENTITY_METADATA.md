# Entity Metadata Fields

This document describes the metadata fields collected per entity (CIK) from SEC data sources.

## Data Sources

### Companyfacts Files (`raw_data/companyfacts/*.json`)
Basic metadata available:
- `cik`: Central Index Key
- `entityName`: Company name

### Submissions Files (`raw_data/submissions/*.json`)
Rich metadata available (extracted and stored in `entity_metadata` table):

## Metadata Fields in `entity_metadata` Table

### Company Identification
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `company_name` | String | Official company name | "Forma Therapeutics Holdings, Inc." |
| `ein` | String | Employer Identification Number | "371657129" |
| `entity_type` | String | Type of entity | "operating" |

### Industry Classification
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `sic` | String | Standard Industrial Classification code | "2836" |
| `sic_description` | String | Description of SIC category | "Biological Products, (No Diagnostic Substances)" |

### Incorporation & Fiscal Info
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `state_of_incorporation` | String | State where company is incorporated | "DE" |
| `fiscal_year_end` | String | Fiscal year end in MMDD format | "1231" (December 31) |

### Filer Classification
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `filer_category` | String | SEC filer category | "Large accelerated filer", "Non-accelerated filer" |

### Contact Information
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `website` | String | Company website URL | "https://example.com" |
| `phone` | String | Company phone number | "617-679-1970" |

### Trading Information
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `tickers` | String (JSON) | Stock ticker symbols (JSON array) | '["FMTX"]' |
| `exchanges` | String (JSON) | Exchange listings (JSON array) | '["NASDAQ"]' |

### Business Address
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `business_street1` | String | Street address line 1 | "300 NORTH BEACON STREET" |
| `business_street2` | String | Street address line 2 | "SUITE 501" |
| `business_city` | String | City | "WATERTOWN" |
| `business_state` | String | State or country code | "MA" |
| `business_zipcode` | String | ZIP/postal code | "02472" |
| `business_country` | String | Country (if specified) | "US" |

### Legacy Fields (Deprecated)
| Field | Type | Description | Status |
|-------|------|-------------|--------|
| `country` | String | Country (old field) | Deprecated, use `business_state` or `business_country` |
| `sector` | String | Business sector | Deprecated, use `sic_description` |

## Examples

### Forma Therapeutics Holdings, Inc. (CIK 0001538927)
```json
{
  "company_name": "Forma Therapeutics Holdings, Inc.",
  "sic": "2836",
  "sic_description": "Biological Products, (No Diagnostic Substances)",
  "state_of_incorporation": "DE",
  "fiscal_year_end": "1231",
  "filer_category": "Large accelerated filer",
  "entity_type": "operating",
  "website": "",
  "phone": "617-679-1970",
  "ein": "371657129",
  "tickers": "[]",
  "exchanges": "[]",
  "business_street1": "300 NORTH BEACON STREET",
  "business_street2": "SUITE 501",
  "business_city": "WATERTOWN",
  "business_state": "MA",
  "business_zipcode": "02472"
}
```

### Legacy Reserves LP (CIK 0001358831)
```json
{
  "company_name": "LEGACY RESERVES LP",
  "sic": "1311",
  "sic_description": "Crude Petroleum & Natural Gas",
  "state_of_incorporation": "DE",
  "fiscal_year_end": "1231",
  "filer_category": "Accelerated filer",
  "entity_type": "operating",
  "phone": "432-689-5200",
  "ein": "000000000",
  "business_state": "TX"
}
```

## Database Schema

The `entity_metadata` table has a 1:1 relationship with the `entities` table:

```sql
CREATE TABLE entity_metadata (
    entity_id INTEGER PRIMARY KEY,
    company_name TEXT,
    sic TEXT,
    sic_description TEXT,
    state_of_incorporation TEXT,
    fiscal_year_end TEXT,
    filer_category TEXT,
    entity_type TEXT,
    website TEXT,
    phone TEXT,
    ein TEXT,
    tickers TEXT,
    exchanges TEXT,
    business_street1 TEXT,
    business_street2 TEXT,
    business_city TEXT,
    business_state TEXT,
    business_zipcode TEXT,
    business_country TEXT,
    country TEXT,  -- deprecated
    sector TEXT,   -- deprecated
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);
```

## Usage in Code

### Extracting Metadata from Submissions
```python
from utils.populate_daily_values import extract_metadata_from_submissions

with open('raw_data/submissions/CIK0001234567.json', 'r') as f:
    data = json.load(f)

metadata = extract_metadata_from_submissions(data)
# Returns a dict with keys matching EntityMetadata column names
```

### Creating/Updating Entity with Metadata
```python
from utils.populate_daily_values import get_or_create_entity

entity = get_or_create_entity(
    cik="0001234567",
    company_name="Example Corp",
    metadata={
        "sic": "7372",
        "sic_description": "Services-Prepackaged Software",
        "state_of_incorporation": "DE",
        "business_city": "San Francisco",
        "business_state": "CA"
    }
)
```

## Migration

To add these fields to an existing database:

```bash
python3 utils/migrate_sqlite_schema.py
```

This will add all new metadata columns as nullable TEXT fields.

## Data Quality Notes

1. **Empty vs Missing**: Many fields may be empty strings ("") rather than NULL
2. **Tickers/Exchanges**: Stored as JSON arrays; parse with `json.loads()` when needed
3. **Phone Numbers**: Not normalized; various formats present
4. **EIN**: Some entities have "000000000" as placeholder
5. **Addresses**: Business address is more consistently populated than mailing address
6. **Fiscal Year End**: Format is MMDD (e.g., "1231" for December 31)

## Future Enhancements

Potential additional metadata to collect:
- Former names (available in submissions as array)
- Mailing address (separate from business address)
- LEI (Legal Entity Identifier)
- Insider transaction flags
- Filing history statistics
