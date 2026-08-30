"""
Security utilities for AI Finance Controller.
Handles:
  - Password hashing & verification (bcrypt via passlib)
  - JWT access token generation & decoding (python-jose)
  - Google ID token verification (google-auth or manual JWKS)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

from jose import JWTError, jwt
import bcrypt

from app.config import settings

logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# Password Hashing
# ---------------------------------------------------------------------------


def hash_password(plain_password: str) -> str:
    """Return bcrypt hash of the plain-text password."""
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False



# ---------------------------------------------------------------------------
# JWT Token Management
# ---------------------------------------------------------------------------
def create_access_token(subject: str, extra_claims: Optional[dict] = None) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: Typically the user's email (unique identifier).
        extra_claims: Optional additional claims to embed (e.g. role, name).

    Returns:
        Signed JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT token.

    Returns:
        The decoded payload dict if valid, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Google ID Token Verification
# ---------------------------------------------------------------------------
def verify_google_token(credential: str) -> Optional[dict]:
    """
    Verify a Google Sign-In credential (ID token) and extract the payload.

    Tries google-auth library first; falls back to unverified decode for
    development environments where GOOGLE_CLIENT_ID is not configured.

    Returns a dict with keys: sub, email, name, picture — or None on failure.
    """
    # --- Production path: verify via google-auth ---------------------
    if settings.GOOGLE_CLIENT_ID:
        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests

            idinfo = google_id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
                clock_skew_in_seconds=10,
            )
            return {
                "sub": idinfo["sub"],
                "email": idinfo["email"],
                "name": idinfo.get("name", idinfo["email"].split("@")[0]),
                "picture": idinfo.get("picture"),
            }
        except Exception as exc:
            logger.warning("Google token verification failed: %s", exc)
            return None

    # --- Development fallback: decode without signature verification --
    # Only for local testing when no GOOGLE_CLIENT_ID is set.
    try:
        import base64, json

        parts = credential.split(".")
        if len(parts) != 3:
            return None

        # Decode payload (add padding if needed)
        padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())

        return {
            "sub": payload.get("sub", "google_dev_sub"),
            "email": payload.get("email", ""),
            "name": payload.get("name", payload.get("email", "").split("@")[0]),
            "picture": payload.get("picture"),
        }
    except Exception as exc:
        logger.warning("Google token dev-decode failed: %s", exc)
        return None
