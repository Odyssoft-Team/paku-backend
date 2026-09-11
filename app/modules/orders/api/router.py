from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_roles
from app.core.db import engine, get_async_session
from app.modules.geo.infra.repository import PostgresDistrictRepository
from app.modules.iam.infra.postgres_user_repository import PostgresUserRepository
from app.modules.orders.api.schemas import (
    AssignmentOut,
    AssignOrderIn,
    ConfirmPaymentIn,
    CreateAdjustmentIn,
    CreateOrderIn,
    OrderOut,
    PatchOrderIn,
    PayOrderIn,
    UpdateStatusIn,
)
from app.modules.orders.app.use_cases import (
    AcceptOrder,
    ArriveOrder,
    AssignOrder,
    CancelOrder,
    CompleteOrder,
    ConfirmCashPayment,
    ConfirmOrderPayment,
    CreateAdjustmentOrder,
    CreateOrderFromCart,
    DepartOrder,
    FailOrderPayment,
    GetOrder,
    GetOrderAdmin,
    ListAllyOrders,
    ListOrders,
    ListOrdersAdmin,
    PatchOrder,
    PayOrder,
    RetryOrderPayment,
    UpdateOrderStatus,
)
from app.modules.orders.domain.order import OrderStatus
from app.modules.orders.infra.culqi_client import CulqiPythonClient
from app.modules.orders.infra.postgres_order_assignment_repository import PostgresOrderAssignmentRepository
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.cart.infra.postgres_cart_repository import PostgresCartRepository
from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository
from app.modules.pets.domain.pet import PetRepository
from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository

router = APIRouter(tags=["orders"], prefix="/orders")
admin_router = APIRouter(tags=["orders-admin"])


# ------------------------------------------------------------------
# Dependencias
# ------------------------------------------------------------------

def get_orders_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresOrderRepository:
    return PostgresOrderRepository(session=session, engine=engine)


def get_assignments_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresOrderAssignmentRepository:
    return PostgresOrderAssignmentRepository(session=session, engine=engine)


def get_pets_repo(session: AsyncSession = Depends(get_async_session)) -> PetRepository:
    return PostgresPetRepository(session=session, engine=engine)


def get_store_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresStoreRepository:
    return PostgresStoreRepository(session=session, engine=engine)


def get_users_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresUserRepository:
    return PostgresUserRepository(session=session, engine=engine)


def get_districts_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresDistrictRepository:
    return PostgresDistrictRepository(session)


def _order_out(order) -> OrderOut:
    return OrderOut(**order.__dict__)


# ------------------------------------------------------------------
# Usuario — CRUD básico
# ------------------------------------------------------------------

@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: CreateOrderIn,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> OrderOut:
    orders_repo = PostgresOrderRepository(session=session, engine=engine)
    cart_repo = PostgresCartRepository(session=session, engine=engine)
    iam_repo = PostgresUserRepository(session=session, engine=engine)
    geo_repo = PostgresDistrictRepository(session=session)

    if payload.address_id is not None:
        addr = await iam_repo.get_address_for_user(user_id=current.id, address_id=payload.address_id)
        if not addr:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    else:
        addr = await iam_repo.get_default_address(user_id=current.id)
        if not addr:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="address_id is required (no default address configured)",
            )

    district = await geo_repo.get_district(addr["district_id"])
    if not district or district.get("active") is not True:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="District is not active")

    snapshot = {
        "district_id": addr["district_id"],
        "address_line": addr["address_line"],
        "reference": addr.get("reference"),
        "building_number": addr.get("building_number"),
        "apartment_number": addr.get("apartment_number"),
        "label": addr.get("label"),
        "type": addr.get("type"),
        "lat": addr["lat"],
        "lng": addr["lng"],
    }

    order = await CreateOrderFromCart(orders_repo=orders_repo, cart_repo=cart_repo).execute(
        user_id=current.id,
        cart_id=payload.cart_id,
        delivery_address_snapshot=snapshot,
    )
    return _order_out(order)


@router.get("", response_model=list[OrderOut])
async def list_orders(
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> list[OrderOut]:
    orders = await ListOrders(orders_repo=repo).execute(user_id=current.id)
    return [_order_out(o) for o in orders]


# IMPORTANTE: esta ruta debe ir ANTES de /{id} para que FastAPI no intente
# parsear "my-assignments" como UUID.
@router.get("/my-assignments", response_model=list[OrderOut])
async def list_my_assignments(
    status_filter: Optional[OrderStatus] = Query(None, alias="status"),
    current: CurrentUser = Depends(require_roles("ally")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> list[OrderOut]:
    """Lista las órdenes asignadas al ally autenticado."""
    orders = await ListAllyOrders(orders_repo=repo).execute(
        ally_id=current.id,
        status=status_filter,
    )
    return [_order_out(o) for o in orders]


@router.get("/{id}", response_model=OrderOut)
async def get_order(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    order = await GetOrder(orders_repo=repo).execute(order_id=id, user_id=current.id)
    return _order_out(order)


@router.patch("/{id}", response_model=OrderOut)
async def patch_order(
    id: UUID,
    payload: PatchOrderIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    order = await PatchOrder(orders_repo=repo).execute(
        order_id=id,
        user_id=current.id,
        status=payload.status,
    )
    return _order_out(order)


@router.post("/{id}/status", response_model=OrderOut)
async def update_status(
    id: UUID,
    payload: UpdateStatusIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    if current.role not in {"admin", "ally"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    order = await UpdateOrderStatus(orders_repo=repo).execute(order_id=id, status=payload.status)
    return _order_out(order)


# ------------------------------------------------------------------
# Ally — transiciones de estado semánticas
# ------------------------------------------------------------------

@router.post("/{id}/accept", response_model=OrderOut)
async def accept_order(
    id: UUID,
    current: CurrentUser = Depends(require_roles("ally")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """Ally acepta el servicio asignado (reservado para flujo futuro)."""
    order = await AcceptOrder(repo=repo).execute(order_id=id, ally_id=current.id)
    return _order_out(order)


@router.post("/{id}/depart", response_model=OrderOut)
async def depart_order(
    id: UUID,
    current: CurrentUser = Depends(require_roles("ally")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """Ally marcó que salió hacia el domicilio del cliente."""
    order = await DepartOrder(repo=repo).execute(order_id=id, ally_id=current.id)
    return _order_out(order)


@router.post("/{id}/arrive", response_model=OrderOut)
async def arrive_order(
    id: UUID,
    current: CurrentUser = Depends(require_roles("ally")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """Ally llegó al domicilio. El servicio comienza."""
    order = await ArriveOrder(repo=repo).execute(order_id=id, ally_id=current.id)
    return _order_out(order)


@router.post("/{id}/complete", response_model=OrderOut)
async def complete_order(
    id: UUID,
    current: CurrentUser = Depends(require_roles("ally")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """Ally marcó el servicio como finalizado."""
    order = await CompleteOrder(repo=repo).execute(order_id=id, ally_id=current.id)
    return _order_out(order)


# ------------------------------------------------------------------
# Admin — gestión de órdenes
# ------------------------------------------------------------------

@admin_router.get("/orders", response_model=list[OrderOut])
async def admin_list_orders(
    status_filter: Optional[OrderStatus] = Query(None, alias="status"),
    ally_id: Optional[UUID] = Query(None),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> list[OrderOut]:
    """Lista todas las órdenes con filtros opcionales."""
    orders = await ListOrdersAdmin(orders_repo=repo).execute(status=status_filter, ally_id=ally_id)
    return [_order_out(o) for o in orders]


@admin_router.get("/orders/{id}", response_model=OrderOut)
async def admin_get_order(
    id: UUID,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    order = await GetOrderAdmin(orders_repo=repo).execute(order_id=id)
    return _order_out(order)


@admin_router.post("/orders/{id}/assign", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def admin_assign_order(
    id: UUID,
    payload: AssignOrderIn,
    current: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
    assignments_repo: PostgresOrderAssignmentRepository = Depends(get_assignments_repo),
) -> AssignmentOut:
    """Asigna un ally a la orden y programa la fecha/hora del servicio."""
    order, assignment = await AssignOrder(
        orders_repo=repo,
        assignments_repo=assignments_repo,
    ).execute(
        order_id=id,
        ally_id=payload.ally_id,
        scheduled_at=payload.scheduled_at,
        assigned_by=current.id,
        notes=payload.notes,
    )
    return AssignmentOut(
        id=assignment.id,
        order_id=assignment.order_id,
        ally_id=assignment.ally_id,
        scheduled_at=assignment.scheduled_at,
        assigned_by=assignment.assigned_by,
        notes=assignment.notes,
        created_at=assignment.created_at,
        order=_order_out(order),
    )


@admin_router.post("/orders/{id}/cancel", response_model=OrderOut)
async def admin_cancel_order(
    id: UUID,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """Cancela una orden desde cualquier estado activo."""
    order = await CancelOrder(repo=repo).execute(order_id=id)
    return _order_out(order)


# ------------------------------------------------------------------
# Recálculo de precio por peso (orden de ajuste)
# ------------------------------------------------------------------

@router.post("/{id}/create-adjustment", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_adjustment_order(
    id: UUID,
    payload: CreateAdjustmentIn,
    _: CurrentUser = Depends(require_roles("admin", "ally")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
    pets_repo: PetRepository = Depends(get_pets_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
) -> OrderOut:
    """
    Crea la orden de ajuste (parent_order_id={id}) por la diferencia de precio detectada
    tras registrar un peso real distinto al declarado. El precio se recalcula aquí de
    nuevo del lado del servidor (no se confía en ningún monto que mande el front) —
    requiere confirmación explícita de admin/ally, no se genera automáticamente.
    """
    adjustment = await CreateAdjustmentOrder(
        orders_repo=repo, pets_repo=pets_repo, store_repo=store_repo,
    ).execute(order_id=id, pet_id=payload.pet_id)
    return _order_out(adjustment)


# ------------------------------------------------------------------
# Endpoints de pago (Culqi)
# ------------------------------------------------------------------

@router.post("/{id}/pay", response_model=OrderOut)
async def pay_order(
    id: UUID,
    payload: PayOrderIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
    users_repo: PostgresUserRepository = Depends(get_users_repo),
    districts_repo: PostgresDistrictRepository = Depends(get_districts_repo),
) -> OrderOut:
    """
    Camino principal de pago: paku-backend orquesta el cobro contra culqi-python
    servidor-a-servidor (el frontend solo manda el token, ya tokenizado con Culqi.js).

    antifraud_details se arma acá del lado del servidor (perfil del usuario + dirección
    de entrega de la orden) — el frontend no lo manda.

    Puede devolver la orden en payment_status=paid, failed o verifying (cuando el
    resultado no pudo confirmarse a tiempo — el cronjob de reconciliación sigue
    intentando en segundo plano, ver app/core/scheduler.py).
    """
    order = await PayOrder(
        orders_repo=repo,
        culqi_client=CulqiPythonClient(),
        users_repo=users_repo,
        districts_repo=districts_repo,
    ).execute(
        order_id=id,
        user_id=current.id,
        email=current.email,
        source_id=payload.source_id,
    )
    return _order_out(order)


@router.post("/{id}/confirm-cash-payment", response_model=OrderOut)
async def confirm_cash_payment(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """
    Confirma el pago en efectivo de una orden. Solo puede ejecutarlo el ally
    asignado a esa orden, al momento de la entrega — no pasa por Culqi.
    """
    order = await ConfirmCashPayment(orders_repo=repo).execute(
        order_id=id,
        ally_id=current.id,
    )
    return _order_out(order)


@router.post("/{id}/confirm-payment", response_model=OrderOut)
async def confirm_payment(
    id: UUID,
    payload: ConfirmPaymentIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """
    Fallback manual (ej. soporte) — el camino principal es POST /{id}/pay.

    Confirma el pago de una orden a partir de un `culqi_charge_id` (chr_...) ya
    obtenido por otra vía. Solo puede ejecutarse una vez por orden (pending → paid).
    """
    order = await ConfirmOrderPayment(orders_repo=repo).execute(
        order_id=id,
        user_id=current.id,
        culqi_charge_id=payload.culqi_charge_id,
    )
    return _order_out(order)


@router.post("/{id}/fail-payment", response_model=OrderOut)
async def fail_payment(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """
    Registra que el cobro fue rechazado por Culqi.
    La orden pasa a payment_status=failed. El usuario puede reintentar el pago.
    """
    order = await FailOrderPayment(orders_repo=repo).execute(
        order_id=id,
        user_id=current.id,
    )
    return _order_out(order)


@router.post("/{id}/retry-payment", response_model=OrderOut)
async def retry_payment(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """
    Permite reintentar el pago de una orden en estado failed.
    Vuelve a payment_status=pending para que el frontend tokenice con otro método.
    """
    order = await RetryOrderPayment(orders_repo=repo).execute(
        order_id=id,
        user_id=current.id,
    )
    return _order_out(order)
