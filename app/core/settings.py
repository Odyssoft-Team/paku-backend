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
    STREAMING_SIGNALING_URL: str = os.getenv("STREAMING_SIGNALING_URL", "wss://stream.paku.com.pe/ws")
    STREAMING_SECRET: str = os.getenv("STREAMING_SECRET", "streaming-secret-change-in-production")
    STREAMING_STUN_URL: str = os.getenv(
        "STREAMING_STUN_URL",
        "stun:stream.paku.com.pe:5349,stun:stream.paku.com.pe:3478",
    )
    STREAMING_TURN_URLS: str = os.getenv(
        "STREAMING_TURN_URLS",
        "turns:stream.paku.com.pe:5349,turn:stream.paku.com.pe:3478",
    )
    STREAMING_TURN_USERNAME: str = os.getenv("STREAMING_TURN_USERNAME", "pakuuser")
    STREAMING_TURN_CREDENTIAL: str = os.getenv("STREAMING_TURN_CREDENTIAL", "pakupassword")

    # Push: "expo" envía push reales (Expo); "mock" solo los escribe en el log. Independiente de ENV para
    # poder probar push en desarrollo sin cambiar DEBUG, logs, etc. Sin valor: "expo" en producción y
    # "mock" en el resto (comportamiento anterior).
    PUSH_PROVIDER: str = (os.getenv("PUSH_PROVIDER") or ("expo" if ENV == "production" else "mock")).strip().lower()

    # Tracking — Google Routes API
    # Dejar vacío para deshabilitar el endpoint GET /tracking/orders/{id}/route.
    # Obtener en: https://console.cloud.google.com/apis/credentials
    GOOGLE_ROUTES_API_KEY: Optional[str] = os.getenv("GOOGLE_ROUTES_API_KEY")

    # Geo — búsqueda de direcciones con Google Places API (New) + Geocoding (feature 0002).
    # Clave de servidor restringida a esas dos APIs. Vacía → /geo/places/* y /geo/geocode
    # responden 503 GEO_UNAVAILABLE y la app sigue sin sugerencias.
    GOOGLE_PLACES_API_KEY: Optional[str] = os.getenv("GOOGLE_PLACES_API_KEY")
    # Límites por usuario para controlar el gasto (contadores en memoria, una instancia).
    GEO_AUTOCOMPLETE_PER_MINUTE: int = int(os.getenv("GEO_AUTOCOMPLETE_PER_MINUTE", "60"))
    GEO_AUTOCOMPLETE_PER_DAY: int = int(os.getenv("GEO_AUTOCOMPLETE_PER_DAY", "300"))
    GEO_LOOKUP_PER_DAY: int = int(os.getenv("GEO_LOOKUP_PER_DAY", "30"))
    GEO_CACHE_TTL_SECONDS: int = int(os.getenv("GEO_CACHE_TTL_SECONDS", "86400"))

    # culqi-python — microservicio de pagos (server-to-server, ver POST /orders/{id}/pay)
    # Producción: nombre del servicio en docker-compose.yml (platform/) + su puerto INTERNO
    # de contenedor (no el publicado al host para nginx) — ver servicio "culqi-backend".
    CULQI_PYTHON_BASE_URL: str = os.getenv("CULQI_PYTHON_BASE_URL", "http://culqi-backend:8080")
    CULQI_PYTHON_SERVICE_API_KEY: str = os.getenv("CULQI_PYTHON_SERVICE_API_KEY", "")


settings = Settings()
