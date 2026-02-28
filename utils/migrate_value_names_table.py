import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'sec.db')

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 1. Rename old table
c.execute('''ALTER TABLE value_names RENAME TO value_names_old''')

# 2. Create new table with updated schema
c.execute('''
CREATE TABLE value_names (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    source INTEGER NOT NULL DEFAULT 1,
    added_on DATETIME NOT NULL,
    valid_until DATETIME
)
''')

# 3. Copy data from old table to new table
c.execute('''
INSERT INTO value_names (id, name, source, added_on, valid_until)
SELECT id, name, 1, ?, NULL FROM value_names_old
''', (datetime.utcnow().isoformat(),))

# 4. Drop old table
c.execute('''DROP TABLE value_names_old''')

conn.commit()
conn.close()
