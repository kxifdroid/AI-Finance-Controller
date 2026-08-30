"""
Authentication API Router.

Endpoints:
  POST /api/auth/register   — Email + password registration
  POST /api/auth/login      — Email + password login
  POST /api/auth/google     — Google One Tap / Sign-In credential verification
  POST /api/auth/demo       — Instant demo login (no credentials required)
  GET  /api/auth/me         — Return current user profile (JWT protected)
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    GoogleAuthRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_google_token,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])
_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Helper: get_current_user (FastAPI dependency)
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Validates the JWT Bearer token and returns the authenticated User object.
    Raises HTTP 401 if the token is absent, invalid, or expired.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email: str = payload.get("sub", "")
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account deactivated.",
        )
    return user


# ---------------------------------------------------------------------------
# Helper: build token response
# ---------------------------------------------------------------------------

def _build_token(user: User, db: Session) -> TokenResponse:
    """Issue a JWT and return a TokenResponse."""
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        subject=user.email,
        extra_claims={"role": user.role, "name": user.name, "auth_provider": user.auth_provider},
    )
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register with Email & Password",
)
def register(body: UserRegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Create a new user account with email and bcrypt-hashed password.
    Returns a JWT access token immediately on success.
    """
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An account with email '{body.email}' already exists.",
        )

    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        name=body.name,
        hashed_password=hash_password(body.password),
        auth_provider="email",
        role="controller",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("New user registered: %s", user.email)
    return _build_token(user, db)


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with Email & Password",
)
def login(body: UserLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Authenticate an email/password user.
    Returns a JWT on success; 401 on invalid credentials.
    """
    user = db.query(User).filter(User.email == body.email).first()

    if not user or user.auth_provider not in ("email", "demo") or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    return _build_token(user, db)


# ---------------------------------------------------------------------------
# POST /api/auth/google
# ---------------------------------------------------------------------------

@router.post(
    "/google",
    response_model=TokenResponse,
    summary="Sign in / Register with Google",
)
def google_auth(body: GoogleAuthRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Verify Google ID token, then find-or-create the user account.
    Supports both:
      - First-time Google users (auto-provisions an account)
      - Returning Google users (updates avatar / name if changed)
    """
    google_info = verify_google_token(body.credential)
    if not google_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google token verification failed. Token may be expired or invalid.",
        )

    email: str = google_info["email"]
    sub: str = google_info["sub"]

    # Find existing user by Google sub (most accurate match)
    user = db.query(User).filter(User.google_sub == sub).first()

    # Fallback: find by email (handles case where user already has email account)
    if not user:
        user = db.query(User).filter(User.email == email).first()

    if user:
        # Update stale profile data
        user.name = google_info.get("name") or user.name
        user.avatar_url = google_info.get("picture") or user.avatar_url
        if not user.google_sub:
            user.google_sub = sub
        user.auth_provider = "google"
    else:
        # First-time Google sign-in — auto-provision
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            name=google_info.get("name") or email.split("@")[0],
            avatar_url=google_info.get("picture"),
            auth_provider="google",
            google_sub=sub,
            role="controller",
        )
        db.add(user)
        logger.info("Google user auto-provisioned: %s", email)

    db.commit()
    db.refresh(user)
    return _build_token(user, db)


# ---------------------------------------------------------------------------
# POST /api/auth/demo
# ---------------------------------------------------------------------------

DEMO_EMAIL = "demo@aifinancecontroller.local"
DEMO_PASSWORD = "Demo@Finance2026!"


@router.post(
    "/demo",
    response_model=TokenResponse,
    summary="Instant Demo Login (no credentials required)",
)
def demo_login(db: Session = Depends(get_db)) -> TokenResponse:
    """
    Create or retrieve the built-in demo user and return a valid JWT.
    Designed for judges, reviewers, and exploratory demos.
    """
    user = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=DEMO_EMAIL,
            name="Senior Finance Controller (Demo)",
            auth_provider="demo",
            hashed_password=hash_password(DEMO_PASSWORD),
            role="admin",
            avatar_url=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Demo user auto-created.")

    return _build_token(user, db)


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Returns the currently authenticated user's profile from the JWT."""
    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# PATCH /api/auth/me
# ---------------------------------------------------------------------------

from app.schemas.auth import ProfileUpdateRequest

@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update user profile",
)
def update_profile(
    body: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserResponse:
    if body.name is not None:
        current_user.name = body.name
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url
    
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# POST /api/auth/me/avatar
# ---------------------------------------------------------------------------

import os
import shutil
from fastapi import UploadFile, File

@router.post(
    "/me/avatar",
    response_model=UserResponse,
    summary="Upload user avatar",
)
def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserResponse:
    """Uploads an avatar image and updates the user's avatar_url."""
    # Ensure directory exists
    avatar_dir = "uploads/avatars"
    os.makedirs(avatar_dir, exist_ok=True)
    
    # Save file with user id to avoid collisions
    ext = file.filename.split('.')[-1] if '.' in file.filename else 'png'
    filename = f"{current_user.id}.{ext}"
    filepath = os.path.join(avatar_dir, filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Update user profile with new URL
    current_user.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    db.refresh(current_user)
    
    return UserResponse.model_validate(current_user)
