# Free, legal, trusted sources of raw (unopinionated) company data

This project already uses SEC EDGAR JSON (US). Below is a curated list of **free**, **legal**, and generally **trusted** sources of raw company data that can be collected via **downloadable files** and/or **APIs**, including options for **non‑US (EU and other) companies**.

> Notes / scope
> - “Raw / unopinionated” here means primary filings, registries, official statistics, official market data feeds, or datasets published by regulators and public institutions.
> - Always review each source’s ToS / licensing and rate limits.
> - Some registries are free to access but may restrict bulk redistribution; treat those as **free-to-access** but verify downstream use.

---

## 1) United States (beyond SEC)

### IRS (US non‑profits)
- **What**: Form 990 filings for non-profits (financials, governance)
- **How**: Bulk downloads and APIs
- **Trust**: US IRS
- **Links**:
  - IRS Tax Exempt Organization Search + bulk data: https://apps.irs.gov/app/eos/
  - IRS 990 e-file data (AWS Open Data / IRS): https://registry.opendata.aws/irs990/

### Federal Register / GovInfo
- **What**: Official publications, rules, notices, some corporate/legal context
- **How**: APIs / bulk
- **Trust**: US Government
- **Links**:
  - GovInfo API: https://api.govinfo.gov/
  - Federal Register API: https://www.federalregister.gov/developers/

### USPTO (patents & trademarks)
- **What**: Patent and trademark applications/assignments; can help entity resolution and R&D indicators
- **How**: Bulk and APIs
- **Trust**: USPTO
- **Links**:
  - USPTO Open Data portal: https://developer.uspto.gov/

---

## 2) Global / multi-country sources (good for non‑US coverage)

### GLEIF (Legal Entity Identifier, LEI)
- **What**: Global LEI reference data (entity identity, relationships)
- **Why it’s useful**: Cross-border identifier for companies; excellent for linking datasets
- **How**: Free API + bulk downloads
- **Trust**: GLEIF (global standards body)
- **Links**:
  - API: https://www.gleif.org/en/lei-solutions/lei-data-access
  - Bulk files: https://www.gleif.org/en/lei-solutions/lei-data-access/gleif-concatenated-file

### OpenCorporates (aggregation)
- **What**: Aggregated company registry data across many jurisdictions
- **How**: API and bulk (licensing varies)
- **Trust**: Widely used; not an official registry (treat as aggregation)
- **Free?**: Has free tiers / free datasets for some use cases; verify licensing for your usage
- **Links**:
  - https://opencorporates.com/info/api

### World Bank / IMF / OECD (macro context)
- **What**: Macroeconomic indicators (not company-level), useful for normalization and analysis
- **How**: APIs / downloads
- **Trust**: International institutions
- **Links**:
  - World Bank API: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation
  - OECD API: https://data.oecd.org/api/sdmx-json-documentation/

---

## 3) European Union (EU): how to collect non‑US company data (free/trusted)

### 3.1 Official Business Registers / interconnection (BRIS)
- **What**: EU Business Registers Interconnection System (BRIS) enables cross-border access to national business registers
- **How**: Access is via member-state registers; availability/bulk access differs by country
- **Trust**: EU member state registrars / EU integration
- **Important limitation**: “Free” can mean free search/access, but bulk extraction and reuse may be restricted.
- **Start here**:
  - e‑Justice portal (BRIS entry points): https://e-justice.europa.eu/

### 3.2 ESMA (European Securities and Markets Authority)
- **What**: Public registers and datasets (e.g., regulated markets, investment firms registers, data for transparency)
- **How**: Downloads; some interfaces are dataset-oriented
- **Trust**: EU regulator
- **Links**:
  - ESMA data and registers: https://www.esma.europa.eu/databases-library

### 3.3 EBA (European Banking Authority)
- **What**: Bank stress test / transparency exercise data; regulatory disclosures (dataset depending on year)
- **How**: Downloads
- **Trust**: EU regulator
- **Links**:
  - EBA Transparency exercise / datasets: https://www.eba.europa.eu/risk-analysis-and-data

### 3.4 EIOPA (insurance)
- **What**: Insurance and pension data, QRT guidance, some datasets
- **How**: Downloads
- **Trust**: EU regulator
- **Links**:
  - https://www.eiopa.europa.eu/tools-and-data_en

### 3.5 EU Open Data Portal
- **What**: Thousands of EU-published datasets; some company-related (procurement, grants, registries)
- **How**: Downloads + APIs
- **Trust**: EU
- **Links**:
  - https://data.europa.eu/

### 3.6 Public procurement (EU-wide)
- **What**: Tender and award notices (buyers, suppliers, amounts, CPV codes)
- **How**: Bulk + APIs (depends on system)
- **Trust**: EU / official procurement publications
- **Links**:
  - TED (Tenders Electronic Daily): https://ted.europa.eu/

---

## 4) National company registries (examples, EU)

These are often the most authoritative sources for “company existence”, directors, registered address, filings, etc. Availability and bulk-legal terms vary.

### United Kingdom
- **Companies House**
  - **What**: Company register, filings metadata, officers, PSC
  - **How**: Free API + bulk downloads
  - **Trust**: UK government
  - **Links**: https://developer.company-information.service.gov.uk/

### France
- **INSEE SIRENE**
  - **What**: Establishment/company identifiers (SIREN/SIRET), legal unit data
  - **How**: API + bulk datasets
  - **Trust**: French national statistics institute
  - **Links**: https://sirene.fr/

### Germany
- **Handelsregister (Commercial Register)**
  - **What**: Official filings for registered businesses
  - **How**: Access via official portal; bulk use may be limited
  - **Trust**: German courts/registry
  - **Start**: https://www.handelsregister.de/

### Netherlands
- **KvK (Dutch Chamber of Commerce)**
  - **What**: Company register
  - **How**: Typically paid products; check for any free datasets and permitted use
  - **Trust**: Official
  - **Start**: https://www.kvk.nl/

### Sweden
- **Bolagsverket**
  - **What**: Company register
  - **How**: Mixed; some services are paid
  - **Trust**: Official
  - **Start**: https://bolagsverket.se/

> Recommendation for EU coverage: prioritize **GLEIF LEI** for global entity identity + selective national registries where APIs/bulk downloads are explicitly free and licensed for reuse.

---

## 5) Other non‑US regions

### Canada
- **SEDAR+ (securities filings)**
  - **What**: Canadian issuer filings
  - **How**: Web access; check for APIs/feeds and terms
  - **Trust**: Canadian securities administrators
  - **Start**: https://www.sedarplus.ca/

### Australia
- **ASIC**
  - **What**: Company registry and filings
  - **How**: Many endpoints are paid; verify any free datasets
  - **Trust**: Official regulator
  - **Start**: https://asic.gov.au/

### Japan
- **EDINET (FSA)**
  - **What**: Japanese financial filings (similar to EDGAR)
  - **How**: API + downloads (EDINET API available)
  - **Trust**: Japan FSA
  - **Start**: https://disclosure2.edinet-fsa.go.jp/

---

## 6) Market identifiers & reference data (useful for joining datasets)

### ISO MIC (Market Identifier Codes)
- **What**: Exchange / trading venue identifiers
- **How**: Download
- **Trust**: ISO standard
- **Links**:
  - https://www.iso20022.org/market-identifier-codes

### FRED (Federal Reserve Economic Data)
- **What**: Macro and financial time series (not company-level)
- **How**: Free API
- **Trust**: Federal Reserve Bank of St. Louis
- **Links**:
  - https://fred.stlouisfed.org/docs/api/fred/

---

## 7) Practical collection guidance (quick)

### A) Prefer primary IDs and build an ID graph
- US: CIK (SEC) + EIN (IRS, where applicable)
- Global: **LEI (GLEIF)**
- EU: national identifiers (e.g., SIREN/SIRET, Companies House number)

Store mappings in a dedicated table (e.g., `entity_identifiers`) to support future joining and dedup.

### B) Collection patterns
- **Bulk first** when available (fewer API calls, easier reproducibility)
- **Incremental updates** via daily/weekly delta files if offered
- **Metadata-first** ingestion: record URL, dataset version, retrieval time, hash, and license text

### C) Compliance checklist (for each source)
- License/ToS allows automated collection and storage
- Rate limits respected
- PII handling: officer/director data can be sensitive depending on jurisdiction
- Provenance recorded for auditability

---

## 8) Suggested next additions for this repo

If you want the “highest value / lowest friction” additions next:
1. **GLEIF LEI** (global): strong for non‑US entity identity and relationships.
2. **Companies House** (UK): excellent free API + bulk.
3. **INSEE SIRENE** (France): strong official identifier dataset.
4. EU procurement (TED) if you want supplier/buyer relationships.

---

## Appendix: What to avoid (common pitfalls)
- Scraping sites that explicitly forbid scraping/bulk download when an API exists.
- “Free” datasets with unclear licensing or restrictive redistribution clauses.
- Vendors offering “free trials” (not truly free for ongoing ingestion).
