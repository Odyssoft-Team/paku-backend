from typing import Dict, List, Optional
from uuid import UUID

from app.modules.commerce.domain.service import Service, ServiceType, Species


# [TECH] Repo in-memory de servicios. Indexa por id y expone list/get para catálogo.
# [NEGOCIO] Guarda el catálogo disponible para que la app pueda mostrar y cotizar servicios.
class InMemoryServiceRepository:
    def __init__(self, services: List[Service]) -> None:
        # [TECH] Carga servicios iniciales en un diccionario {id: Service}. Output: repo listo.
        # [NEGOCIO] Deja el catálogo preparado para consultas rápidas por identificador.
        self._by_id: Dict[UUID, Service] = {s.id: s for s in services}

    def list_services(self) -> List[Service]:
        # [TECH] Devuelve todos los servicios del catálogo (incluye base/addon; el filtrado ocurre en use cases).
        # [NEGOCIO] Permite obtener la lista de servicios disponibles para mostrar en la app.
        return list(self._by_id.values())

    def get_service(self, service_id: UUID) -> Optional[Service]:
        # [TECH] Busca un servicio por id. Input: service_id. Output: Service o None.
        # [NEGOCIO] Permite encontrar un servicio específico del catálogo por su identificador.
        return self._by_id.get(service_id)


# [TECH] IDs fijos para seed del catálogo (usados en tests/demos). Relacionados a base/addons.
# [NEGOCIO] Identificadores estables para servicios de ejemplo que la app puede cotizar.
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
            allowed_breeds=["husky", "labrador"],
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


# [TECH] Wrapper de módulo para listar servicios desde el repo por defecto. Output: List[Service].
# [NEGOCIO] Punto único para obtener el catálogo actual de servicios disponibles.
def list_services() -> List[Service]:
    return _default_repo.list_services()


# [TECH] Wrapper de módulo para obtener un servicio por id. Input: service_id. Output: Service/None.
# [NEGOCIO] Permite consultar un servicio puntual del catálogo por su identificador.
def get_service(service_id: UUID) -> Optional[Service]:
    return _default_repo.get_service(service_id)
