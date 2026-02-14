import os
from typing import Optional


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Paku Backend")
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # Database
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

    # GCS
    GCS_BUCKET: Optional[str] = os.getenv("GCS_BUCKET")
    _GCS_SIGNED_URL_TTL_RAW: str = os.getenv("GCS_SIGNED_URL_TTL_SECONDS", "300")
    try:
        GCS_SIGNED_URL_TTL_SECONDS: int = int(_GCS_SIGNED_URL_TTL_RAW)
    except ValueError:
        GCS_SIGNED_URL_TTL_SECONDS: int = 300


settings = Settings()
