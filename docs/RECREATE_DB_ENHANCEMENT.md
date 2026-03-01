# Database Reset Script Enhancement

## Overview

The `utils/recreate_sqlite_db.py` script has been enhanced with additional features to make database management safer and more informative.

## New Features

### 1. **Backup Creation (`--backup` flag)**
Create a timestamped backup before resetting the database:

```bash
python3 utils/recreate_sqlite_db.py --backup --yes
```

- Backup filename format: `sec.db.backup_YYYYMMDD_HHMMSS`
- Shows backup file size
- Safe to run multiple times (creates unique backups each time)

### 2. **Database Information Display**
Before confirmation, the script now shows:
- Existing database size (if present)
- List of all current tables

Example output:
```
Existing tables (7):
  - daily_values
  - dates
  - entities
  - entity_metadata
  - file_processing
  - units
  - value_names

⚠️  WARNING: Database exists (2.45 MB)
```

### 3. **Graceful Error Handling**
If the database is corrupted or inaccessible:
- Script detects the error
- Falls back to deleting the entire file
- Creates a fresh database
- Continues with table creation

Example:
```
⚠️  Could not drop tables gracefully: database disk image is malformed
🗑️  Deleting database file and recreating from scratch...
```

### 4. **Enhanced Output**
- Progress indicators with emojis (🔄, 🔨, ✓)
- Shows recreated tables after completion
- Displays final database location

## Usage Examples

### Basic Reset (with confirmation)
```bash
python3 utils/recreate_sqlite_db.py
```

### Skip Confirmation
```bash
python3 utils/recreate_sqlite_db.py --yes
# or
python3 utils/recreate_sqlite_db.py -y
```

### Create Backup Before Reset
```bash
python3 utils/recreate_sqlite_db.py --backup --yes
# or
python3 utils/recreate_sqlite_db.py -b -y
```

### View Help
```bash
python3 utils/recreate_sqlite_db.py --help
```

## What Gets Reset

The script resets **ALL** database tables:
1. `daily_values` - All daily financial values
2. `dates` - All date records
3. `entities` - All entity records
4. `entity_metadata` - All entity metadata (33 fields)
5. `file_processing` - All file processing history
6. `units` - All unit definitions
7. `value_names` - All value name definitions

## Safety Features

1. **Confirmation Prompt**: Requires user confirmation unless `--yes` is used
2. **Size Display**: Shows database size before deletion
3. **Backup Option**: Optional timestamped backups
4. **WAL/SHM Cleanup**: Removes SQLite journal files that can cause issues
5. **Error Recovery**: Handles corrupted databases gracefully

## Technical Details

### Database Tables
All tables are defined in SQLAlchemy models:
- `models/daily_values.py`
- `models/dates.py`
- `models/entities.py`
- `models/entity_metadata.py` (33 metadata fields)
- `models/file_processing.py`
- `models/units.py`
- `models/value_names.py`

### Reset Process
1. Show existing tables
2. Prompt for confirmation (unless `--yes`)
3. Create backup (if `--backup`)
4. Clean up WAL/SHM files
5. Try graceful `DROP TABLE` for all tables
6. If error, delete entire database file
7. Create all tables from models
8. Display summary

### Error Handling
- **Corrupted Database**: Deletes file and recreates
- **Missing Directory**: Creates `data/` directory if needed
- **Backup Failure**: Warns but continues
- **WAL/SHM Removal**: Non-fatal if locked

## When to Use

### Use This Script When:
- Adding new models/tables to the project
- Testing migrations before deployment
- Cleaning up corrupted database
- Starting fresh with empty tables
- Development/testing iterations

### Don't Use When:
- In production (would lose all data!)
- Wanting to preserve existing data
- Only adding columns (use `migrate_sqlite_schema.py` instead)

## Related Scripts

- `utils/migrate_sqlite_schema.py` - Add columns without losing data
- `utils/populate_daily_values.py` - Import SEC data
- `utils/populate_value_names.py` - Import value names

## Example Session

```bash
$ python3 utils/recreate_sqlite_db.py --backup --yes

Existing tables (7):
  - daily_values
  - dates
  - entities
  - entity_metadata
  - file_processing
  - units
  - value_names
  
✓ Backup created: data/sec.db.backup_20260301_083000 (2.45 MB)

🔄 Dropping all tables...
🔨 Recreating all tables from models...

✓ Database reset complete!

Recreated tables (7):
  - daily_values
  - dates
  - entities
  - entity_metadata
  - file_processing
  - units
  - value_names

Database location: /Users/stefan/Desktop/sec_test/data/sec.db
```

## Notes

- Backups accumulate in `data/` directory (not auto-deleted)
- Database path: `data/sec.db`
- All metadata fields are included in fresh schema
- No data migration - complete reset only
