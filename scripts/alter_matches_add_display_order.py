"""Adds display_order column to matches table.

Run with: python scripts/alter_matches_add_display_order.py
"""
import sqlalchemy as sa
from sqlalchemy import create_engine, MetaData, Table, Column, Integer
from app.db.session import get_db
from app.db.base import Base

if __name__ == "__main__":
    engine = create_engine("sqlite:///finance_controller.db")
    meta = MetaData()
    meta.reflect(bind=engine)
    matches = Table("matches", meta, autoload_with=engine)
    if "display_order" not in matches.c:
        with engine.begin() as conn:
            conn.execute(sa.text("ALTER TABLE matches ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0;"))
    print("display_order column added (if not present).")
