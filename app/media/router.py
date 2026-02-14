from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import CurrentUser, get_current_user
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
)

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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to sign upload URL") from exc

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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to sign read URL") from exc

    return SignedReadResponse(read_url=read_url, expires_in=expires_in)
