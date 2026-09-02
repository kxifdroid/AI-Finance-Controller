"""
Database session and engine management.
Supports both SQLite (local development) and PostgreSQL.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from app.db.base import Base

# Configure engine with SQLite-specific connect_args if needed
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all database tables and perform lightweight column migrations if needed."""
    # Import all models to ensure they are registered with Base.metadata
    import app.models  # noqa: F401
    # Also import approval service to register ApprovalRequest model
    import app.services.approval  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # SQLite lightweight migration resilience for added columns
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        if "matches" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("matches")]
            if "display_order" not in columns:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE matches ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0;"))
    except Exception:
        pass

