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


settings = Settings()
