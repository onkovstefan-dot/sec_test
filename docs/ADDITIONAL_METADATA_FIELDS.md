# Additional Metadata Fields Available in Submissions

## Analysis of 10 Random Submissions Files

After examining 10 additional random submissions files, here are the fields we're **currently capturing** and fields we're **missing**:

## Currently Captured ✅

- `cik` - Central Index Key
- `name` / `entityName` / `companyName` → `company_name`
- `sic` → `sic`
- `sicDescription` → `sic_description`
- `stateOfIncorporation` → `state_of_incorporation`
- `fiscalYearEnd` → `fiscal_year_end`
- `category` → `filer_category`
- `entityType` → `entity_type`
- `website` → `website`
- `phone` → `phone`
- `ein` → `ein`
- `tickers` → `tickers` (JSON array)
- `exchanges` → `exchanges` (JSON array)
- `addresses.business.*` → `business_*` fields

## Missing Fields (Available but Not Captured) 🔴

### 1. LEI (Legal Entity Identifier)
- **Field**: `lei`
- **Type**: String (or null)
- **Example**: Could be a 20-character alphanumeric code
- **Usage**: International identifier for legal entities
- **Note**: Most entities have `null`, but some may have values

### 2. Description
- **Field**: `description`
- **Type**: String
- **Example**: Usually empty, but could contain entity description
- **Usage**: Company/entity description text

### 3. Investor Website
- **Field**: `investorWebsite`
- **Type**: String (URL)
- **Example**: "https://ir.example.com"
- **Usage**: Separate from main website, specifically for investor relations

### 4. State of Incorporation Description
- **Field**: `stateOfIncorporationDescription`
- **Type**: String
- **Example**: "DE", "Cayman Islands", "OR"
- **Usage**: Human-readable description of incorporation location (vs code)
- **Note**: Can show foreign countries like "Cayman Islands" (code: "E9")

### 5. Owner Organization
- **Field**: `ownerOrg`
- **Type**: String or null
- **Example**: Could be parent company name
- **Usage**: Identifies if entity is owned by another organization

### 6. Insider Transaction Flags
- **Field**: `insiderTransactionForOwnerExists`
- **Type**: Integer (0 or 1)
- **Usage**: Indicates if insider transactions exist where this entity is the owner

- **Field**: `insiderTransactionForIssuerExists`
- **Type**: Integer (0 or 1)
- **Usage**: Indicates if insider transactions exist where this entity is the issuer

### 7. Flags
- **Field**: `flags`
- **Type**: String
- **Example**: Usually empty string
- **Usage**: Unknown - possibly regulatory flags or special designations

### 8. Former Names
- **Field**: `formerNames`
- **Type**: Array of objects
- **Structure**: 
  ```json
  [
    {
      "name": "ANDERSON FISHER LLC",
      "from": "2019-02-14T00:00:00.000Z",
      "to": "2021-02-04T00:00:00.000Z"
    }
  ]
  ```
- **Usage**: Track name changes over time with effective dates

### 9. Mailing Address (Separate from Business)
- **Fields**: `addresses.mailing.*`
- **Available fields**:
  - `street1`, `street2`
  - `city`
  - `stateOrCountry`
  - `zipCode`
  - `stateOrCountryDescription`
  - `isForeignLocation` (0 or 1)
  - `foreignStateTerritory`
  - `country`
  - `countryCode`
- **Usage**: Separate mailing address (may differ from business address)

## Recommendations for Additional Fields to Capture

### High Priority (Useful & Frequently Populated)

1. **`lei`** - Legal Entity Identifier
   - Column: `lei` (String, nullable)
   - Reason: International standard identifier

2. **`stateOfIncorporationDescription`** 
   - Column: `state_of_incorporation_description` (String, nullable)
   - Reason: Shows full country names for foreign entities (e.g., "Cayman Islands" vs "E9")

3. **`investorWebsite`**
   - Column: `investor_website` (String, nullable)
   - Reason: Separate from main website, useful for investor relations

4. **`insiderTransactionForOwnerExists`**
   - Column: `has_insider_transactions_as_owner` (Integer/Boolean, nullable)
   - Reason: Indicates regulatory activity

5. **`insiderTransactionForIssuerExists`**
   - Column: `has_insider_transactions_as_issuer` (Integer/Boolean, nullable)
   - Reason: Indicates regulatory activity

6. **Former Names** (most valuable)
   - Option A: Store as JSON string in single column `former_names`
   - Option B: Create separate `former_names` table with entity_id FK
   - Reason: Track corporate name changes with dates

7. **Mailing Address** (if different from business)
   - Columns: `mailing_street1`, `mailing_street2`, `mailing_city`, `mailing_state`, `mailing_zipcode`
   - Reason: Complete address records

### Medium Priority (Less Frequently Used)

8. **`ownerOrg`**
   - Column: `owner_organization` (String, nullable)
   - Reason: Shows parent company relationships

9. **`description`**
   - Column: `entity_description` (Text, nullable)
   - Reason: May contain useful descriptive text (usually empty)

10. **`flags`**
    - Column: `sec_flags` (String, nullable)
    - Reason: Unknown purpose but might be useful

## Implementation Priority

### Immediate (Easy Wins)
Simple string fields that are easy to add:
- `lei`
- `stateOfIncorporationDescription` → `state_of_incorporation_description`
- `investorWebsite` → `investor_website`
- `ownerOrg` → `owner_organization`
- `insiderTransactionForOwnerExists` → `has_insider_transactions_as_owner`
- `insiderTransactionForIssuerExists` → `has_insider_transactions_as_issuer`
- `flags` → `sec_flags`
- `description` → `entity_description`

### Phase 2 (Structured Data)
Mailing address fields (mirror business address structure):
- `mailing_street1`, `mailing_street2`, `mailing_city`, `mailing_state`, `mailing_zipcode`, `mailing_country`

### Phase 3 (Complex Data)
Former names - requires decision on storage strategy:
- Option A: Store as JSON array in `former_names` column
- Option B: Create separate `entity_former_names` table (more normalized)

## Example: Complete Metadata for Human Investing LLC (CIK 0001767513)

```json
{
  "company_name": "Human Investing LLC",
  "ein": "743130983",
  "entity_type": "other",
  "sic": "",
  "sic_description": "",
  "state_of_incorporation": "OR",
  "state_of_incorporation_description": "OR",
  "fiscal_year_end": "1231",
  "filer_category": "",
  "phone": "(503) 905-3100",
  "website": "",
  "investor_website": "",
  "lei": null,
  "owner_organization": "",
  "has_insider_transactions_as_owner": 0,
  "has_insider_transactions_as_issuer": 0,
  "sec_flags": "",
  "entity_description": "",
  "business_street1": "6000 MEADOWS RD",
  "business_street2": "SUITE 105",
  "business_city": "LAKE OSWEGO",
  "business_state": "OR",
  "business_zipcode": "97035",
  "mailing_street1": "6000 MEADOWS RD",
  "mailing_street2": "SUITE 105",
  "mailing_city": "LAKE OSWEGO",
  "mailing_state": "OR",
  "mailing_zipcode": "97035",
  "former_names": [
    {
      "name": "ANDERSON FISHER LLC",
      "from": "2019-02-14",
      "to": "2021-02-04"
    }
  ]
}
```

## Data Quality Notes

1. **LEI**: Mostly null in the sampled files
2. **Description**: Usually empty string
3. **Investor Website**: Usually empty for smaller entities
4. **State Description**: Very useful for foreign entities (shows country names)
5. **Former Names**: Valuable for tracking corporate history and M&A activity
6. **Mailing Address**: Often same as business address but can differ
7. **Insider Transaction Flags**: Binary indicators (0 or 1)
8. **Owner Org**: Mostly null or empty, but could be valuable for subsidiaries

## Estimated Storage Impact

Adding these fields would increase the `entity_metadata` table by:
- 8 simple string/integer fields (immediate)
- 6 address fields (mailing address)
- 1 JSON field or separate table (former names)

Total: ~15 additional columns in entity_metadata table, all nullable.
