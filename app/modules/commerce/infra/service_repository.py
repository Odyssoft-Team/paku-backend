from typing import Dict, List, Optional
from uuid import UUID

from app.modules.commerce.domain.service import Service, ServiceType, Species


class InMemoryServiceRepository:
    def __init__(self, services: List[Service]) -> None:
        self._by_id: Dict[UUID, Service] = {s.id: s for s in services}

    def list_services(self) -> List[Service]:
        return list(self._by_id.values())

    def get_service(self, service_id: UUID) -> Optional[Service]:
        return self._by_id.get(service_id)


_BASE_DOG_BATH = UUID("11111111-1111-1111-1111-111111111111")
_ADDON_DOG_NAILS = UUID("22222222-2222-2222-2222-222222222222")
_BASE_CAT_GROOM = UUID("33333333-3333-3333-3333-333333333333")
_ADDON_DOG_TEETH = UUID("44444444-4444-4444-4444-444444444444")

_default_repo = InMemoryServiceRepository(
    services=[
        Service(
            id=_BASE_DOG_BATH,
            name="Bano base (perro)",
            type=ServiceType.base,
            species=Species.dog,
            allowed_breeds=None,
            requires=None,
            is_active=True,
        ),
        Service(
            id=_ADDON_DOG_NAILS,
            name="Corte de unas (addon)",
            type=ServiceType.addon,
            species=Species.dog,
            allowed_breeds=None,
            requires=[_BASE_DOG_BATH],
            is_active=True,
        ),
        Service(
            id=_BASE_CAT_GROOM,
            name="Aseo base (gato)",
            type=ServiceType.base,
            species=Species.cat,
            allowed_breeds=None,
            requires=None,
            is_active=True,
        ),
        Service(
            id=_ADDON_DOG_TEETH,
            name="Limpieza dental (addon)",
            type=ServiceType.addon,
            species=Species.dog,
            allowed_breeds=None,
            requires=[_BASE_DOG_BATH],
            is_active=True,
        ),
    ]
)


def list_services() -> List[Service]:
    return _default_repo.list_services()


def get_service(service_id: UUID) -> Optional[Service]:
    return _default_repo.get_service(service_id)
