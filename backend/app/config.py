"""
Configuration settings for AI Finance Controller.
Uses pydantic-settings to load environment variables with sane defaults.
"""

from typing import List, Optional, Union
import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "AI Finance Controller"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    parsed = json.loads(v_stripped)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed]
                except Exception:
                    pass
            # Split comma separated origins or single item
            return [origin.strip() for origin in v_stripped.split(",") if origin.strip()]
        return [str(x).strip() for x in v]

    # Database
    DATABASE_URL: str = "sqlite:///./finance_controller.db"

    # LLM Settings
    LLM_PROVIDER: str = Field(default="mock", description="mock | openai | anthropic | gemini")
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    MODEL_NAME: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.0
    LLM_TIMEOUT_SECONDS: int = 15

    # Reconciliation Thresholds
    AUTO_MATCH_THRESHOLD: float = 0.90
    AI_REVIEW_THRESHOLD: float = 0.70
    
    # Candidate Generation & Blocking Tolerances
    # Note: Blocking weights (candidate filtering) are kept separate from decision scoring weights
    # because blocking is an early, cheap candidate filter while decision scoring is the final metric.
    BLOCKING_AMOUNT_WEIGHT: float = 0.6
    BLOCKING_DATE_WEIGHT: float = 0.4
    AMOUNT_TOLERANCE_PCT: float = 0.05      # 5% relative variance tolerance
    AMOUNT_TOLERANCE_FIXED: float = 50.0   # Fixed currency difference tolerance
    DATE_TOLERANCE_DAYS: int = 5            # Max days discrepancy for candidate matching
    
    # Deterministic Decision Scoring Weights (Sum = 1.0)
    WEIGHT_AMOUNT: float = 0.40
    WEIGHT_REFERENCE: float = 0.25
    WEIGHT_DATE: float = 0.20
    WEIGHT_CUSTOMER: float = 0.15
    SCORING_AMOUNT_DECAY_RATE: float = 10.0 # math.exp(-10.0 * pct_diff)
    SCORING_DATE_STEP_WEIGHTS: List[float] = [0.95, 0.90, 0.35]

    # Tolerances
    FEE_VARIANCE_MIN_PCT: float = 0.01      # 1% standard gateway fee floor
    FEE_VARIANCE_MAX_PCT: float = 0.05      # 5% standard gateway fee ceiling
    SETTLEMENT_DATE_TOLERANCE_DAYS: int = 3 # Tighter window for bank settlement matching

    # Many-to-One Settlement Matching
    MANY_TO_ONE_MAX_GROUP_SIZE: int = 10     # Max records in subset-sum group
    MANY_TO_ONE_AMOUNT_TOLERANCE: float = 0.01  # Absolute tolerance for sum matching

    # AI Investigation Thresholds
    AI_INVESTIGATION_AUTO_THRESHOLD: float = 0.95  # Above this -> auto-accept AI suggestion
    AI_INVESTIGATION_REVIEW_THRESHOLD: float = 0.75  # Below this -> always require human review

    # GST / Tax Configuration (India)
    GST_RATE_ON_GATEWAY_FEE: float = 0.18   # 18% GST on gateway fees

    # Materiality Gate & Exception Severities
    MATERIALITY_AUTO_CLEAR_CEILING: float = 5000.0  # Max amount allowed to auto-clear without review (₹5,000 ceiling)
    SEVERITY_LOW_THRESHOLD: float = 500.0
    SEVERITY_MEDIUM_THRESHOLD: float = 10000.0
    SEVERITY_HIGH_THRESHOLD: float = 100000.0

    # Storage paths
    DATA_DIR: str = "./data"

    # JWT Authentication
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_use_openssl_rand_hex_32"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
