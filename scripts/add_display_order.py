import sqlite3
import os

DB_PATH = os.path.join(os.getcwd(), 'finance_controller.db')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
# Check if column exists
cursor.execute("PRAGMA table_info(matches)")
cols = [row[1] for row in cursor.fetchall()]
if 'display_order' not in cols:
    cursor.execute("ALTER TABLE matches ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0;")
    conn.commit()
    print('Added display_order column')
else:
    print('display_order already exists')
conn.close()
