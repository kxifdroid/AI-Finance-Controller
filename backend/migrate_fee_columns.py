"""
One-time migration: add fee_classification and fee_breakdown_json columns to matches table.
Safe to run multiple times (checks for column existence first).
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "finance_controller.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("PRAGMA table_info(matches)")
existing = [row[1] for row in cur.fetchall()]
print("Existing columns:", existing)

added = []
if "fee_classification" not in existing:
    cur.execute("ALTER TABLE matches ADD COLUMN fee_classification VARCHAR(32)")
    added.append("fee_classification")

if "fee_breakdown_json" not in existing:
    cur.execute("ALTER TABLE matches ADD COLUMN fee_breakdown_json TEXT")
    added.append("fee_breakdown_json")

conn.commit()
conn.close()

if added:
    print(f"Added columns: {added}")
else:
    print("Columns already present — nothing to do.")
