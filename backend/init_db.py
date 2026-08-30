#!/usr/bin/env python
"""Initialize database with all tables."""
from app.db.session import init_db

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully")
