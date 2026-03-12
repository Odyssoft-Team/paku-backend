import re
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

import google.auth
import google.auth.iam
import google.auth.transport.requests
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


def parse_object_name(object_name: str) -> tuple[str, UUID]:
    """
    Parsea un object_name ya validado y devuelve (prefix, entity_id).
    prefix es 'users' o 'pets'.
    Lanza ValueError si el formato no es reconocido.
    """
    validate_object_name(object_name)
    parts = object_name.split("/")
    # Formato garantizado: {prefix}/{uuid}/profile_...
    prefix = parts[0]
    try:
        entity_id = UUID(parts[1])
    except (IndexError, ValueError) as exc:
        raise ValueError("Invalid object_name: cannot extract entity_id") from exc
    return prefix, entity_id


def _get_signing_credentials():
    """
    Devuelve credentials con capacidad de firma compatibles con generate_signed_url v4,
    tanto en entornos con JSON key como en Compute Engine / Cloud Run / GKE.

    - Con JSON key (GOOGLE_APPLICATION_CREDENTIALS): las credenciales ADC ya tienen
      signer con private key → se usan directamente.
    - En Compute Engine sin JSON key: las credenciales ADC son de tipo
      google.auth.compute_engine.Credentials (solo token, sin private key).
      En ese caso se construye un google.auth.iam.Signer que delega la firma
      a la IAM signBlob API usando la identidad de la VM.
      Requiere que el service account tenga el rol "Service Account Token Creator".
    """
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    # Refrescar para tener un token válido antes de usarlo en el signer
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)

    service_account_email = getattr(credentials, "service_account_email", None)
    if not service_account_email:
        raise RuntimeError(
            "Cannot determine service account email from current credentials. "
            "Ensure the VM has an associated service account."
        )

    # Si ya tiene signer con private key (JSON key), devolver directamente
    if hasattr(credentials, "signer") and credentials.signer is not None:
        return credentials

    # Compute Engine: delegar firma a IAM signBlob API (no necesita private key local)
    from google.oauth2 import service_account as _sa

    signer = google.auth.iam.Signer(
        request=request,
        credentials=credentials,
        service_account_email=service_account_email,
    )
    signing_credentials = _sa.Credentials(
        signer=signer,
        service_account_email=service_account_email,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return signing_credentials


def generate_signed_upload_url(object_name: str, content_type: str, expires_in: int) -> str:
    signing_credentials = _get_signing_credentials()
    client = storage.Client()
    bucket = client.bucket(get_bucket_name())
    blob = bucket.blob(object_name)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=expires_in),
        method="PUT",
        content_type=content_type,
        credentials=signing_credentials,
    )


def generate_signed_read_url(object_name: str, expires_in: int) -> str:
    signing_credentials = _get_signing_credentials()
    client = storage.Client()
    bucket = client.bucket(get_bucket_name())
    blob = bucket.blob(object_name)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=expires_in),
        method="GET",
        credentials=signing_credentials,
    )
