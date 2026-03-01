# Quick Reference: recreate_sqlite_db.py

## One-Line Summary
Safely reset all database tables with optional backup and enhanced error handling.

## Quick Commands

```bash
# Interactive (with prompts)
python3 utils/recreate_sqlite_db.py

# Auto-confirm
python3 utils/recreate_sqlite_db.py --yes

# With backup
python3 utils/recreate_sqlite_db.py --backup --yes

# Help
python3 utils/recreate_sqlite_db.py --help
```

## What It Does

✓ Drops all 7 database tables  
✓ Recreates tables from SQLAlchemy models  
✓ Includes all 33 entity metadata fields  
✓ Optional timestamped backups  
✓ Handles corrupted databases  

## Tables Reset

1. `daily_values`
2. `dates`
3. `entities`
4. `entity_metadata` (33 fields)
5. `file_processing`
6. `units`
7. `value_names`

## When to Use

✓ Adding new models/tables  
✓ Testing migrations  
✓ Fixing corrupted database  
✓ Starting fresh  
✗ Production (data loss!)  
✗ To preserve data (use migrate instead)  

## Flags

- `--yes` / `-y` - Skip confirmation
- `--backup` / `-b` - Create backup first

## Output Example

```
Existing tables (7):
  - daily_values
  - dates
  ...

✓ Backup created: sec.db.backup_20260301_083000 (2.45 MB)
🔄 Dropping all tables...
🔨 Recreating all tables from models...
✓ Database reset complete!
```

## Safety Features

- Shows database size before reset
- Lists existing tables
- Requires confirmation (unless --yes)
- Optional timestamped backups
- Graceful error recovery

## See Also

- `docs/RECREATE_DB_ENHANCEMENT.md` - Full documentation
- `utils/migrate_sqlite_schema.py` - Add columns without data loss
