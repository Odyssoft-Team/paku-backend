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
        obj_prefix, obj_entity_id = parse_object_name(payload.object_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Verificar que el object_name pertenece realmente a la entidad declarada
    expected_prefix = "users" if payload.entity_type == MediaEntityType.user else "pets"
    if obj_prefix != expected_prefix or obj_entity_id != payload.entity_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="object_name does not belong to the specified entity",
        )

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

        # User es frozen dataclass: construir nueva instancia con el campo actualizado
        from app.modules.iam.domain.user import User
        updated_user = User(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            phone=user.phone,
            first_name=user.first_name,
            last_name=user.last_name,
            sex=user.sex,
            birth_date=user.birth_date,
            profile_completed=user.profile_completed,
            dni=user.dni,
            address=user.address,
            profile_photo_url=payload.object_name,  # único campo que cambia
        )
        await repo.update(updated_user)

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

        # Pet es frozen dataclass: construir nueva instancia con el campo actualizado
        from app.modules.pets.domain.pet import Pet
        updated_pet = Pet(
            id=pet.id,
            owner_id=pet.owner_id,
            name=pet.name,
            species=pet.species,
            breed=pet.breed,
            sex=pet.sex,
            birth_date=pet.birth_date,
            notes=pet.notes,
            created_at=pet.created_at,
            photo_url=payload.object_name,  # único campo que cambia
            weight_kg=pet.weight_kg,
            updated_at=pet.updated_at,
            sterilized=pet.sterilized,
            size=pet.size,
            activity_level=pet.activity_level,
            coat_type=pet.coat_type,
            skin_sensitivity=pet.skin_sensitivity,
            bath_behavior=pet.bath_behavior,
            tolerates_drying=pet.tolerates_drying,
            tolerates_nail_clipping=pet.tolerates_nail_clipping,
            vaccines_up_to_date=pet.vaccines_up_to_date,
            grooming_frequency=pet.grooming_frequency,
            receive_reminders=pet.receive_reminders,
            antiparasitic=pet.antiparasitic,
            antiparasitic_interval=pet.antiparasitic_interval,
            special_shampoo=pet.special_shampoo,
        )
        await pet_repo.update(updated_pet)

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
