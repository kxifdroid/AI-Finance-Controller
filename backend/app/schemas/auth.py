"""
Pydantic schemas for authentication endpoints.
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Jane Doe"])
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, examples=["SecurePass123!"])


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    """Receives the Google credential (ID token JWT string) from the frontend."""
    credential: str = Field(..., description="Google One Tap / Sign-In button credential JWT")


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    avatar_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """Safe user profile returned after successful auth."""
    id: str
    email: str
    name: str
    role: str
    auth_provider: str
    avatar_url: Optional[str] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Standard Bearer token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
