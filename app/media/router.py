from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.db import engine, get_async_session
from app.media.gcs import (
    ALLOWED_CONTENT_TYPES,
    build_object_name,
    generate_signed_read_url,
    generate_signed_upload_url,
    get_ttl_seconds,
    parse_object_name,
    validate_object_name,
)
from app.media.schemas import (
    MediaEntityType,
    SignedReadRequest,
    SignedReadResponse,
    SignedUploadRequest,
    SignedUploadResponse,
    ConfirmProfilePhotoRequest,
    ConfirmProfilePhotoResponse,
)
from app.modules.iam.infra.postgres_user_repository import PostgresUserRepository
from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository

router = APIRouter(tags=["media"])


@router.post("/media/signed-upload", response_model=SignedUploadResponse, status_code=status.HTTP_201_CREATED)
async def create_signed_upload(
    payload: SignedUploadRequest,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> SignedUploadResponse:
    if payload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported content_type")

    # --- Ownership validation ---
    try:
        current_id = UUID(str(current.id))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid current user id") from exc

    if payload.entity_type == MediaEntityType.user:
        if current_id != payload.entity_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot upload media for another user",
            )
    else:
        # entity_type == pet: la mascota debe existir y pertenecer al current_user
        pet_repo = PostgresPetRepository(session=session, engine=engine)
        pet = await pet_repo.get_by_id(payload.entity_id)
        if pet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
        if pet.owner_id != current_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot upload media for a pet you do not own",
            )

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
    session: AsyncSession = Depends(get_async_session),
) -> SignedReadResponse:
    # Validar formato antes de hacer cualquier consulta
    try:
        validate_object_name(payload.object_name)
        prefix, entity_id = parse_object_name(payload.object_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # --- Ownership validation ---
    try:
        current_id = UUID(str(current.id))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid current user id") from exc

    if prefix == "users":
        if current_id != entity_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot read media for another user",
            )
    else:
        # prefix == "pets": verificar que la mascota existe y pertenece al current_user
        pet_repo = PostgresPetRepository(session=session, engine=engine)
        pet = await pet_repo.get_by_id(entity_id)
        if pet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
        if pet.owner_id != current_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot read media for a pet you do not own",
            )

    try:
        expires_in = get_ttl_seconds()
        read_url = generate_signed_read_url(
            object_name=payload.object_name,
            expires_in=expires_in,
        )
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
    session: AsyncSession = Depends(get_async_session),
) -> ConfirmProfilePhotoResponse:
    """
    Confirma una foto ya subida a GCS y la asocia a la entidad.

    - user: guarda object_name en users.profile_photo_url
    - pet: guarda object_name en pets.photo_url
    """
    # Validación básica de object_name
    try:
        validate_object_name(payload.object_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Ownership mínimo + persistencia
    if payload.entity_type == MediaEntityType.user:
        # Normalizar current.id (puede ser UUID o string según tu auth)
        try:
            current_id = UUID(str(current.id))
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid current user id") from exc

        if current_id != payload.entity_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot set profile photo for another user",
            )

        repo = PostgresUserRepository(session=session, engine=engine)
        user = await repo.get_by_id(payload.entity_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Guardamos object_name (aunque el campo se llame profile_photo_url)
        user.profile_photo_url = payload.object_name
        await repo.update(user)

    else:
        # entity_type == pet
        try:
            current_id = UUID(str(current.id))
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid current user id") from exc

        pet_repo = PostgresPetRepository(session=session, engine=engine)
        pet = await pet_repo.get_by_id(payload.entity_id)
        if pet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")

        if pet.owner_id != current_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot set profile photo for a pet you do not own",
            )

        # Guardamos object_name en pets.photo_url
        pet.photo_url = payload.object_name
        await pet_repo.update(pet)

    # Devolver read_url listo para mostrar en frontend
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
