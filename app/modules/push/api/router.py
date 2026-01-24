from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.db import engine, get_async_session
from app.modules.push.api.schemas import DeviceOut, DeviceRegisterIn
from app.modules.push.app.use_cases import DeactivateDevice, ListDevices, RegisterDevice
from app.modules.push.infra.postgres_device_repository import PostgresDeviceTokenRepository


router = APIRouter(tags=["push"], prefix="/push")


def get_push_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresDeviceTokenRepository:
    return PostgresDeviceTokenRepository(session=session, engine=engine)


@router.post("/devices", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceRegisterIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresDeviceTokenRepository = Depends(get_push_repo),
) -> DeviceOut:
    device = await RegisterDevice(repo=repo).execute(user_id=current.id, platform=payload.platform, token=payload.token)
    return DeviceOut(**device.__dict__)


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresDeviceTokenRepository = Depends(get_push_repo),
) -> list[DeviceOut]:
    devices = await ListDevices(repo=repo).execute(user_id=current.id)
    return [DeviceOut(**d.__dict__) for d in devices]


@router.delete("/devices/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_device(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresDeviceTokenRepository = Depends(get_push_repo),
) -> None:
    await DeactivateDevice(repo=repo).execute(user_id=current.id, device_id=id)
    return None
