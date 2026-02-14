from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class MediaEntityType(str, Enum):
    user = "user"
    pet = "pet"


class SignedUploadRequest(BaseModel):
    entity_type: MediaEntityType = Field(..., description="Target entity type: user or pet")
    entity_id: UUID = Field(..., description="User or pet UUID")
    content_type: str = Field(..., description="image/webp, image/jpeg, image/png")


class SignedUploadResponse(BaseModel):
    upload_url: str
    object_name: str
    content_type: str
    expires_in: int


class SignedReadRequest(BaseModel):
    object_name: str = Field(..., description="GCS object name to read")


class SignedReadResponse(BaseModel):
    read_url: str
    expires_in: int
