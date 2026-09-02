import sqlite3
import os

for db_path in ['finance_controller.db', 'backend/finance_controller.db']:
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        print(db_path, "tables count:", len(tables))
        if 'matches' in tables:
            cur.execute("PRAGMA table_info(matches);")
            cols = [r[1] for r in cur.fetchall()]
            print(db_path, "has display_order:", 'display_order' in cols)
            print(db_path, "columns:", cols)
        conn.close()
