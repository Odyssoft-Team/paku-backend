import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv(".env.local", override=True)  # local overrides — ignored if file absent
load_dotenv()  # fallback: .env (Docker lo inyecta directamente, no necesita este archivo)


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Paku Backend")
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    ROOT_PATH: str = os.getenv("ROOT_PATH", "")

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

    # Firebase (social auth — Google, Apple, Facebook)
    FIREBASE_CREDENTIALS_JSON: Optional[str] = os.getenv("FIREBASE_CREDENTIALS_JSON")

    # Streaming / WebRTC
    # STREAMING_DEV: replace static TURN credentials with dynamic generation in production.
    STREAMING_SIGNALING_URL: str = os.getenv("STREAMING_SIGNALING_URL", "wss://stream.dev-qa.site/ws")
    STREAMING_SECRET: str = os.getenv("STREAMING_SECRET", "streaming-secret-change-in-production")
    STREAMING_STUN_URL: str      = os.getenv("STREAMING_STUN_URL",      "stun:stun.l.google.com:19302")
    STREAMING_TURN_URLS: str     = os.getenv(
        "STREAMING_TURN_URLS",
        "turn:stream.dev-qa.site:3478?transport=udp,turn:stream.dev-qa.site:3478?transport=tcp",
    )
    STREAMING_TURN_USERNAME: str = os.getenv("STREAMING_TURN_USERNAME", "webrtc")
    STREAMING_TURN_CREDENTIAL: str = os.getenv("STREAMING_TURN_CREDENTIAL", "webrtc123")

    # Tracking — Google Routes API
    # Dejar vacío para deshabilitar el endpoint GET /tracking/orders/{id}/route.
    # Obtener en: https://console.cloud.google.com/apis/credentials
    GOOGLE_ROUTES_API_KEY: Optional[str] = os.getenv("GOOGLE_ROUTES_API_KEY")


settings = Settings()
