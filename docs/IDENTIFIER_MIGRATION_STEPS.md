# Migration steps (fresh DB, no migrations): Global company identifier + strict matching

Goal
- Keep `entities.id` as the **int primary key** referenced by large fact tables (e.g. `daily_values`).
- Add a stable **canonical UUID** per entity for internal/global uniqueness (not used as FK).
- Add a new `entity_identifiers` table to support **strict exact matching** across sources via `(scheme, value)`.
- Make the system suitable for **large non‑US coverage** by not relying on a US-only identifier field.

---

## 1) Data model changes (what changed)

### A) `entities`
- Keep:
  - `id` (INTEGER PK)
- Add:
  - `canonical_uuid` (TEXT, unique, indexed, non-null)
- Change:
  - `cik` becomes **nullable** and is treated as a **legacy convenience field** only.
    - Strict uniqueness/identity is enforced via `entity_identifiers`.

### B) `entity_identifiers` (new)
- Columns:
  - `id` INTEGER PK
  - `entity_id` INTEGER FK -> `entities.id` (CASCADE)
  - `scheme` TEXT (e.g. `sec_cik`, `gleif_lei`, `gb_companies_house`)
  - `value` TEXT (normalized)
  - `country` TEXT nullable
  - `issuer` TEXT nullable
- Constraints:
  - Unique(`scheme`, `value`) to enforce strict matching
  - Indexes on `entity_id` and `scheme`

### C) Fact tables remain int-FK first
- No changes are required to `daily_values` (or similarly large tables) to use UUIDs.
- Those tables continue to reference `entities.id`.

---

## 2) Fresh DB creation steps (recommended path)

1. Stop the app / jobs that use `data/sec.db`.
2. Move aside the existing DB for backup, e.g. rename to `sec.db.bak`.
3. Ensure the code imports all models before calling `Base.metadata.create_all(engine)`.
   - In this repo, `models/__init__.py` now imports the model modules so table metadata is registered.
4. Recreate the DB by running the existing ingestion job (`utils/populate_daily_values.py`) or any bootstrap that calls `Base.metadata.create_all(engine)`.
5. Verify tables exist:
   - `entities` includes `canonical_uuid`
   - `entity_identifiers` exists

Because this is a fresh DB, you do not need data migrations; ingestion will populate identifiers.

---

## 3) Ingestion changes (how strict matching is implemented)

### A) Canonical entity ID
- On entity creation, generate `canonical_uuid = uuid4()`.
- On reading an existing entity row, backfill `canonical_uuid` if missing (defensive for older DBs/tests).

### B) Strict identifier inserts
- For each ingested identifier, insert into `entity_identifiers`.
- Enforce uniqueness: if the same `(scheme,value)` is already linked to a different entity, raise an error.
- For SEC ingestion, also populate the legacy `entities.cik` field (optional) when scheme is `sec_cik`.

### C) Normalization rules
- `sec_cik`: normalize to 10-digit zero padded numeric string
- `gleif_lei`: normalize to uppercased string
- Other schemes: trim whitespace (add per-country rules later)

---

## 4) Extending to non‑US sources later (strict matching plan)

When you add a new data source, implement the same pattern:

1. Decide the scheme name (stable, lowercase):
   - `gleif_lei`
   - `gb_companies_house`
   - `fr_siren`
   - `de_handelsregister` (only if you have a stable identifier)
2. Normalize the identifier value.
3. Resolve entity by identifier first:
   - Lookup `entity_identifiers` where `(scheme,value)` matches.
   - If present -> get `entity_id`.
   - If absent -> create entity with a new `canonical_uuid`, then insert `entity_identifiers` row.

This enables exact matching without relying on names and without relying on `entities.cik`.

---

## 5) Backfill steps (only if you ever reuse an existing DB)

If you decide not to start fresh in the future, backfill can be done with a one-off script:

1. Add `canonical_uuid` column (SQLite requires table rebuild or a safe ALTER if nullable).
2. Create `entity_identifiers` table.
3. For each existing entity:
   - Set `canonical_uuid` if null
   - Insert `entity_identifiers(sec_cik, cik)`
4. Add unique constraints (or create with constraints upfront and handle conflicts)

---

## 6) Sanity checks

- Insert two different entities with the same `(scheme,value)` should fail.
- `daily_values` continues to join via `entities.id`.
- `entities.cik` may be NULL for non‑SEC entities.

---

## 7) Files changed in this repo

- `models/entities.py`: added `canonical_uuid`
- `models/entity_identifiers.py`: new table
- `models/__init__.py`: imports models to register metadata
- `utils/populate_daily_values.py`: ensures canonical UUID + inserts `(sec_cik, value)` into `entity_identifiers`
