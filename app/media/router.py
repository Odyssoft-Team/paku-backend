from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user

# IMPORTANTE:
# Cambia este import por el dependency REAL que tu proyecto usa para obtener AsyncSession.
# Ejemplos comunes:
# - from app.core.db import get_session, engine
# - from app.core.db import get_db, engine
# - from app.core.db import get_async_session, engine
from app.core.db import engine, get_session  # <-- AJUSTA ESTO

from app.media.gcs import (
    ALLOWED_CONTENT_TYPES,
    build_object_name,
    generate_signed_read_url,
    generate_signed_upload_url,
    get_ttl_seconds,
    validate_object_name,
)
from app.media.schemas import (
    SignedReadRequest,
    SignedReadResponse,
    SignedUploadRequest,
    SignedUploadResponse,
    MediaEntityType,
    ConfirmProfilePhotoRequest,
    ConfirmProfilePhotoResponse,
)

from app.modules.iam.infra.postgres_user_repository import PostgresUserRepository

router = APIRouter(tags=["media"])


@router.post("/media/signed-upload", response_model=SignedUploadResponse, status_code=status.HTTP_201_CREATED)
async def create_signed_upload(
    payload: SignedUploadRequest,
    current: CurrentUser = Depends(get_current_user),
) -> SignedUploadResponse:
    if payload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported content_type")

    # TODO: if entity_type=user -> entity_id must match current_user.id
    # TODO: if entity_type=pet -> validate in DB that pet_id belongs to current_user

    try:
        object_name = build_object_name(
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            content_type=payload.content_type,
        )
        expires_in = get_ttl_seconds()
        upload_url = generate_signed_upload_url(
            object_name=object_name,
            content_type=payload.content_type,
            expires_in=expires_in,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sign upload URL",
        ) from exc

    return SignedUploadResponse(
        upload_url=upload_url,
        object_name=object_name,
        content_type=payload.content_type,
        expires_in=expires_in,
    )


@router.post("/media/signed-read", response_model=SignedReadResponse)
async def create_signed_read(
    payload: SignedReadRequest,
    current: CurrentUser = Depends(get_current_user),
) -> SignedReadResponse:
    # TODO: validate object_name ownership (user/pet) against current_user
    # Recomendado futuro: leer object_name desde BD por user/pet, no aceptar string libre

    try:
        validate_object_name(payload.object_name)
        expires_in = get_ttl_seconds()
        read_url = generate_signed_read_url(
            object_name=payload.object_name,
            expires_in=expires_in,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sign read URL",
        ) from exc

    return SignedReadResponse(read_url=read_url, expires_in=expires_in)


@router.post("/media/confirm-profile-photo", response_model=ConfirmProfilePhotoResponse)
async def confirm_profile_photo(
    payload: ConfirmProfilePhotoRequest,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),  # <-- AJUSTA si tu dependency se llama distinto
) -> ConfirmProfilePhotoResponse:
    """
    Confirma una foto ya subida a GCS y la asocia a la entidad (MVP: solo user).
    Guarda object_name en users.profile_photo_url y retorna un read_url firmado.
    """

    try:
        validate_object_name(payload.object_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Ownership mínimo (user)
    if payload.entity_type == MediaEntityType.user:
        # Nota: current.id puede ser UUID o string; normalizamos
        try:
            current_id = UUID(str(current.id))
        except Exception:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid current user id")

        if current_id != payload.entity_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot set profile photo for another user")

        repo = PostgresUserRepository(session=session, engine=engine)
        user = await repo.get_by_id(payload.entity_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Guardamos el object_name (aunque el campo se llame profile_photo_url)
        user.profile_photo_url = payload.object_name
        await repo.update(user)

    else:
        # TODO: Implementar para pets:
        # - validar en DB que pet_id pertenece al current_user
        # - guardar object_name en el modelo Pet
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Pet profile photo not implemented yet")

    expires_in = get_ttl_seconds()
    try:
        read_url = generate_signed_read_url(payload.object_name, expires_in=expires_in)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sign read URL",
        ) from exc

    return ConfirmProfilePhotoResponse(
        object_name=payload.object_name,
        read_url=read_url,
        expires_in=expires_in,
    )
