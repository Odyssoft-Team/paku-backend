import re
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from google.cloud import storage

from app.core.settings import settings
from app.media.schemas import MediaEntityType

ALLOWED_CONTENT_TYPES: Final[dict[str, str]] = {
    "image/webp": "webp",
    "image/jpeg": "jpg",
    "image/png": "png",
}

OBJECT_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(users|pets)/[0-9a-fA-F-]{36}/profile_\d{8}T\d{6}\d{6}Z\.(webp|jpg|png)$"
)


def get_bucket_name() -> str:
    if not settings.GCS_BUCKET:
        raise ValueError("GCS_BUCKET is not configured")
    return settings.GCS_BUCKET


def get_ttl_seconds() -> int:
    ttl = settings.GCS_SIGNED_URL_TTL_SECONDS
    if ttl < 60:
        return 60
    if ttl > 900:
        return 900
    return ttl


def resolve_prefix(entity_type: MediaEntityType) -> str:
    if entity_type == MediaEntityType.user:
        return "users"
    return "pets"


def build_object_name(entity_type: MediaEntityType, entity_id: UUID, content_type: str) -> str:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Unsupported content_type")
    extension = ALLOWED_CONTENT_TYPES[content_type]
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    prefix = resolve_prefix(entity_type)
    return f"{prefix}/{entity_id}/profile_{timestamp}.{extension}"


def validate_object_name(object_name: str) -> None:
    if not object_name or ".." in object_name or object_name.startswith("/") or "\\" in object_name:
        raise ValueError("Invalid object_name")
    if not OBJECT_NAME_PATTERN.match(object_name):
        raise ValueError("Invalid object_name")


def generate_signed_upload_url(object_name: str, content_type: str, expires_in: int) -> str:
    client = storage.Client()
    bucket = client.bucket(get_bucket_name())
    blob = bucket.blob(object_name)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=expires_in),
        method="PUT",
        content_type=content_type,
    )


def generate_signed_read_url(object_name: str, expires_in: int) -> str:
    client = storage.Client()
    bucket = client.bucket(get_bucket_name())
    blob = bucket.blob(object_name)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=expires_in),
        method="GET",
    )
