"""
User model for authentication and role-based access.
Stores email-password users AND Google OAuth users in the same table.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Identity
    email: str = Column(String(255), unique=True, nullable=False, index=True)
    name: str = Column(String(255), nullable=False, default="")
    avatar_url: str = Column(String(1024), nullable=True)

    # Auth provider: "email" | "google" | "demo"
    auth_provider: str = Column(String(32), nullable=False, default="email")

    # Password (bcrypt hash) — NULL for Google / demo users
    hashed_password: str = Column(String(128), nullable=True)

    # Google subject ID — NULL for email users
    google_sub: str = Column(String(255), nullable=True, unique=True)

    # Role-based access: "controller" | "auditor" | "admin" | "demo"
    role: str = Column(String(32), nullable=False, default="controller")

    is_active: bool = Column(Boolean, default=True)

    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    last_login_at: datetime = Column(DateTime(timezone=True), nullable=True)
