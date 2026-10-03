"""
Router del módulo tracking.

Endpoints:
  POST /tracking/orders/{order_id}/location
    → Groomer reporta su posición actual. Solo accesible con rol "groomer".

  GET /tracking/orders/{order_id}/current
    → Devuelve la última posición conocida del groomer + destino del servicio.
      Accesible por el cliente dueño de la orden, el groomer asignado o un admin.

  GET /tracking/orders/{order_id}/route
    → Devuelve polyline + ETA calculados por Google Routes API.
      Mismo control de acceso que /current.
      Devuelve 501 si GOOGLE_ROUTES_API_KEY no está configurada.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_roles
from app.core.db import engine, get_async_session
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.tracking.api.schemas import (
    CurrentLocationOut,
    LocationPoint,
    ReportLocationIn,
    ReportLocationOut,
    RouteOut,
)
from app.modules.tracking.infra.postgres_location_store import PostgresLocationStore
from app.modules.tracking.use_cases.get_current import GetCurrent
from app.modules.tracking.use_cases.get_route import GetRoute
from app.modules.tracking.use_cases.report_location import ReportLocation

router = APIRouter(tags=["tracking"], prefix="/tracking")


def _get_orders_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresOrderRepository:
    return PostgresOrderRepository(session=session, engine=engine)


def _get_location_store(session: AsyncSession = Depends(get_async_session)) -> PostgresLocationStore:
    return PostgresLocationStore(session=session)


# ---------------------------------------------------------------------------
# POST /tracking/orders/{order_id}/location
# ---------------------------------------------------------------------------

@router.post(
    "/orders/{order_id}/location",
    response_model=ReportLocationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Groomer reporta su posición actual",
)
async def report_location(
    order_id: UUID,
    payload: ReportLocationIn,
    current: CurrentUser = Depends(require_roles("groomer")),
    orders_repo: PostgresOrderRepository = Depends(_get_orders_repo),
    location_store: PostgresLocationStore = Depends(_get_location_store),
) -> ReportLocationOut:
    """
    El groomer envía su lat/lng actual mientras está en camino.

    - Solo accesible con rol **groomer**.
    - La orden debe estar en estado `on_the_way` o `in_service`.
    - El groomer debe ser el asignado a la orden.
    - La posición se persiste en PostgreSQL (compatible con múltiples instancias).
    - Intervalo recomendado desde el app: cada 10 segundos.
    """
    location = await ReportLocation(orders_repo=orders_repo, location_store=location_store).execute(
        order_id=order_id,
        groomer_id=current.id,
        lat=payload.lat,
        lng=payload.lng,
        accuracy_m=payload.accuracy_m,
    )
    return ReportLocationOut(
        order_id=location.order_id,
        lat=location.lat,
        lng=location.lng,
        recorded_at=location.recorded_at,
    )


# ---------------------------------------------------------------------------
# GET /tracking/orders/{order_id}/current
# ---------------------------------------------------------------------------

@router.get(
    "/orders/{order_id}/current",
    response_model=CurrentLocationOut,
    summary="Última posición conocida del groomer + destino",
)
async def get_current(
    order_id: UUID,
    current: CurrentUser = Depends(get_current_user),
    orders_repo: PostgresOrderRepository = Depends(_get_orders_repo),
    location_store: PostgresLocationStore = Depends(_get_location_store),
) -> CurrentLocationOut:
    """
    Devuelve la última posición reportada por el groomer y las coordenadas
    del domicilio del cliente.

    - Accesible por el **cliente** dueño de la orden, el **groomer** asignado o un **admin**.
    - La orden debe estar en estado `on_the_way` o `in_service`.
    - `groomer_location` puede ser `null` si el groomer aún no envió su primera posición.
    - `staleness_seconds` indica la antigüedad de los datos de posición.

    **Uso recomendado:** el frontend hace polling cada 5 segundos.
    """
    data = await GetCurrent(orders_repo=orders_repo, location_store=location_store).execute(
        order_id=order_id,
        requester_id=current.id,
        requester_role=current.role,
    )

    groomer_loc = data["groomer_location"]
    groomer_point: LocationPoint | None = None
    if groomer_loc is not None:
        groomer_point = LocationPoint(
            lat=groomer_loc.lat,
            lng=groomer_loc.lng,
            accuracy_m=groomer_loc.accuracy_m,
            recorded_at=groomer_loc.recorded_at,
        )

    dest = data["destination"]
    return CurrentLocationOut(
        order_id=data["order_id"],
        order_status=data["order_status"],
        groomer_location=groomer_point,
        destination=LocationPoint(lat=dest["lat"], lng=dest["lng"]),
        staleness_seconds=data["staleness_seconds"],
    )


# ---------------------------------------------------------------------------
# GET /tracking/orders/{order_id}/route
# ---------------------------------------------------------------------------

@router.get(
    "/orders/{order_id}/route",
    response_model=RouteOut,
    summary="Ruta y ETA calculados por Google Routes API",
)
async def get_route(
    order_id: UUID,
    current: CurrentUser = Depends(get_current_user),
    orders_repo: PostgresOrderRepository = Depends(_get_orders_repo),
    location_store: PostgresLocationStore = Depends(_get_location_store),
) -> RouteOut:
    """
    Devuelve la polyline codificada y el tiempo estimado de llegada (ETA)
    calculados en tiempo real por Google Routes API.

    - Mismo control de acceso que `/current`.
    - Devuelve **HTTP 501** si `GOOGLE_ROUTES_API_KEY` no está configurada.
    - Si el groomer aún no reportó posición, devuelve el destino sin ruta
      (`eta_seconds`, `polyline` y `distance_meters` serán `null`).
    """
    data = await GetRoute(orders_repo=orders_repo, location_store=location_store).execute(
        order_id=order_id,
        requester_id=current.id,
        requester_role=current.role,
    )

    groomer_loc = data["groomer_location"]
    groomer_point: LocationPoint | None = None
    if groomer_loc is not None:
        groomer_point = LocationPoint(
            lat=groomer_loc.lat,
            lng=groomer_loc.lng,
            accuracy_m=groomer_loc.accuracy_m,
            recorded_at=groomer_loc.recorded_at,
        )

    dest = data["destination"]
    return RouteOut(
        order_id=data["order_id"],
        groomer_location=groomer_point,
        destination=LocationPoint(lat=dest["lat"], lng=dest["lng"]),
        eta_seconds=data["eta_seconds"],
        eta_display=data["eta_display"],
        polyline=data["polyline"],
        distance_meters=data["distance_meters"],
    )
