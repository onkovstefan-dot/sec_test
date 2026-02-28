import os
import json
import sqlite3

# Path to submissions directory
SUBMISSIONS_DIR = os.path.join(os.path.dirname(__file__), "raw_data", "submissions")
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "sec.db")

# Connect to SQLite database (creates if not exists)
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Create table with flattened columns based on sample JSON structure
c.execute(
    """
CREATE TABLE IF NOT EXISTS submissions_flat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    cik TEXT,
    entityType TEXT,
    sic TEXT,
    sicDescription TEXT,
    ownerOrg TEXT,
    insiderTransactionForOwnerExists INTEGER,
    insiderTransactionForIssuerExists INTEGER,
    name TEXT,
    tickers TEXT,
    exchanges TEXT,
    ein TEXT,
    lei TEXT,
    description TEXT,
    website TEXT,
    investorWebsite TEXT,
    category TEXT,
    fiscalYearEnd TEXT,
    stateOfIncorporation TEXT,
    stateOfIncorporationDescription TEXT,
    mailing_street1 TEXT,
    mailing_street2 TEXT,
    mailing_city TEXT,
    mailing_stateOrCountry TEXT,
    mailing_zipCode TEXT,
    mailing_stateOrCountryDescription TEXT,
    mailing_isForeignLocation TEXT,
    mailing_foreignStateTerritory TEXT,
    mailing_country TEXT,
    mailing_countryCode TEXT,
    business_street1 TEXT,
    business_street2 TEXT,
    business_city TEXT,
    business_stateOrCountry TEXT,
    business_zipCode TEXT,
    business_stateOrCountryDescription TEXT,
    business_isForeignLocation TEXT,
    business_foreignStateTerritory TEXT,
    business_country TEXT,
    business_countryCode TEXT,
    phone TEXT,
    flags TEXT,
    filings_recent_accessionNumber TEXT,
    filings_recent_filingDate TEXT,
    filings_recent_reportDate TEXT,
    filings_recent_acceptanceDateTime TEXT,
    filings_recent_act TEXT,
    filings_recent_form TEXT,
    filings_recent_fileNumber TEXT,
    filings_recent_filmNumber TEXT,
    filings_recent_items TEXT,
    filings_recent_core_type TEXT,
    filings_recent_size TEXT,
    filings_recent_isXBRL TEXT,
    filings_recent_isInlineXBRL TEXT,
    filings_recent_primaryDocument TEXT,
    filings_recent_primaryDocDescription TEXT
)
"""
)
conn.commit()

# Iterate over all JSON files in submissions directory
for filename in os.listdir(SUBMISSIONS_DIR):
    if filename.endswith(".json"):
        file_path = os.path.join(SUBMISSIONS_DIR, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Flatten fields
        addresses = data.get("addresses", {})
        mailing = addresses.get("mailing", {})
        business = addresses.get("business", {})
        filings = data.get("filings", {})
        recent = filings.get("recent", {})
        # Insert into flattened table
        columns = [
            "filename",
            "cik",
            "entityType",
            "sic",
            "sicDescription",
            "ownerOrg",
            "insiderTransactionForOwnerExists",
            "insiderTransactionForIssuerExists",
            "name",
            "tickers",
            "exchanges",
            "ein",
            "lei",
            "description",
            "website",
            "investorWebsite",
            "category",
            "fiscalYearEnd",
            "stateOfIncorporation",
            "stateOfIncorporationDescription",
            "mailing_street1",
            "mailing_street2",
            "mailing_city",
            "mailing_stateOrCountry",
            "mailing_zipCode",
            "mailing_stateOrCountryDescription",
            "mailing_isForeignLocation",
            "mailing_foreignStateTerritory",
            "mailing_country",
            "mailing_countryCode",
            "business_street1",
            "business_street2",
            "business_city",
            "business_stateOrCountry",
            "business_zipCode",
            "business_stateOrCountryDescription",
            "business_isForeignLocation",
            "business_foreignStateTerritory",
            "business_country",
            "business_countryCode",
            "phone",
            "flags",
            "filings_recent_accessionNumber",
            "filings_recent_filingDate",
            "filings_recent_reportDate",
            "filings_recent_acceptanceDateTime",
            "filings_recent_act",
            "filings_recent_form",
            "filings_recent_fileNumber",
            "filings_recent_filmNumber",
            "filings_recent_items",
            "filings_recent_core_type",
            "filings_recent_size",
            "filings_recent_isXBRL",
            "filings_recent_isInlineXBRL",
            "filings_recent_primaryDocument",
            "filings_recent_primaryDocDescription",
        ]
        values = [
            filename,
            data.get("cik"),
            data.get("entityType"),
            data.get("sic"),
            data.get("sicDescription"),
            data.get("ownerOrg"),
            data.get("insiderTransactionForOwnerExists"),
            data.get("insiderTransactionForIssuerExists"),
            data.get("name"),
            json.dumps(data.get("tickers", [])),
            json.dumps(data.get("exchanges", [])),
            data.get("ein"),
            data.get("lei"),
            data.get("description"),
            data.get("website"),
            data.get("investorWebsite"),
            data.get("category"),
            data.get("fiscalYearEnd"),
            data.get("stateOfIncorporation"),
            data.get("stateOfIncorporationDescription"),
            mailing.get("street1"),
            mailing.get("street2"),
            mailing.get("city"),
            mailing.get("stateOrCountry"),
            mailing.get("zipCode"),
            mailing.get("stateOrCountryDescription"),
            mailing.get("isForeignLocation"),
            mailing.get("foreignStateTerritory"),
            mailing.get("country"),
            mailing.get("countryCode"),
            business.get("street1"),
            business.get("street2"),
            business.get("city"),
            business.get("stateOrCountry"),
            business.get("zipCode"),
            business.get("stateOrCountryDescription"),
            business.get("isForeignLocation"),
            business.get("foreignStateTerritory"),
            business.get("country"),
            business.get("countryCode"),
            data.get("phone"),
            data.get("flags"),
            json.dumps(recent.get("accessionNumber", [])),
            json.dumps(recent.get("filingDate", [])),
            json.dumps(recent.get("reportDate", [])),
            json.dumps(recent.get("acceptanceDateTime", [])),
            json.dumps(recent.get("act", [])),
            json.dumps(recent.get("form", [])),
            json.dumps(recent.get("fileNumber", [])),
            json.dumps(recent.get("filmNumber", [])),
            json.dumps(recent.get("items", [])),
            json.dumps(recent.get("core_type", [])),
            json.dumps(recent.get("size", [])),
            json.dumps(recent.get("isXBRL", [])),
            json.dumps(recent.get("isInlineXBRL", [])),
            json.dumps(recent.get("primaryDocument", [])),
            json.dumps(recent.get("primaryDocDescription", [])),
        ]
        c.execute(
            f"""
            INSERT INTO submissions_flat ({', '.join(columns)})
            VALUES ({', '.join(['?' for _ in columns])})
        """,
            values,
        )

conn.commit()
conn.close()
