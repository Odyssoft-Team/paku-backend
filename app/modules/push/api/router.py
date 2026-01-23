from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.auth import CurrentUser, get_current_user
from app.modules.push.api.schemas import DeviceOut, DeviceRegisterIn
from app.modules.push.app.use_cases import DeactivateDevice, ListDevices, RegisterDevice
from app.modules.push.infra.device_repository import InMemoryDeviceTokenRepository


router = APIRouter(tags=["push"], prefix="/push")
_repo = InMemoryDeviceTokenRepository()


@router.post("/devices", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
async def register_device(payload: DeviceRegisterIn, current: CurrentUser = Depends(get_current_user)) -> DeviceOut:
    device = await RegisterDevice(repo=_repo).execute(user_id=current.id, platform=payload.platform, token=payload.token)
    return DeviceOut(**device.__dict__)


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(current: CurrentUser = Depends(get_current_user)) -> list[DeviceOut]:
    devices = await ListDevices(repo=_repo).execute(user_id=current.id)
    return [DeviceOut(**d.__dict__) for d in devices]


@router.delete("/devices/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_device(id: UUID, current: CurrentUser = Depends(get_current_user)) -> None:
    await DeactivateDevice(repo=_repo).execute(user_id=current.id, device_id=id)
    return None
