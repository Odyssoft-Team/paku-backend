from datetime import date
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
    DelayReportIn,
    DelayReportOut,
    GroomerOrderOut,
    SkipIn,
    NextStepIn,
    OrderOut,
    OrderPhotoIn,
    OrderPhotoOut,
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
    ListGroomerOrders,
    ListOrders,
    ListOrdersAdmin,
    PayOrder,
    RetryOrderPayment,
    UpdateOrderStatus,
)
from app.modules.orders.app.use_cases_impl.admin_orders import GetGroomerOrder
from app.modules.orders.app.use_cases_impl.groomer_view import build_groomer_view
from app.modules.orders.app.use_cases_impl.service_flow import (
    AddOrderPhoto,
    ListOrderPhotos,
    MarkAddonDone,
    NextServiceStep,
)
from app.modules.orders.app.use_cases_impl.stops import ListDelayReports, ReportDelay, SkipStop
from app.modules.orders.infra.postgres_delay_report_repository import PostgresDelayReportRepository
from app.modules.orders.infra.postgres_order_photo_repository import PostgresOrderPhotoRepository
from app.modules.orders.domain.order import OrderStatus
from app.core.culqi_client import CulqiPythonClient
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


def get_holds_repo(session: AsyncSession = Depends(get_async_session)):
    from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository

    return PostgresHoldRepository(session=session, engine=engine)


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

    from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository

    holds_repo = PostgresHoldRepository(session=session, engine=engine)
    order = await CreateOrderFromCart(orders_repo=orders_repo, cart_repo=cart_repo, holds_repo=holds_repo).execute(
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
async def _groomer_order_out(order, *, pets_repo, users_repo, store_repo) -> GroomerOrderOut:
    from app.media.gcs import to_signed_read_url_or_none

    view = await build_groomer_view(
        order,
        pets_repo=pets_repo,
        users_repo=users_repo,
        store_repo=store_repo,
        signed_url=to_signed_read_url_or_none,
    )
    return GroomerOrderOut(**order.__dict__, **view)


@router.get("/my-assignments", response_model=list[GroomerOrderOut])
async def list_my_assignments(
    status_filter: Optional[OrderStatus] = Query(None, alias="status"),
    day: Optional[date] = Query(None, alias="date", description="YYYY-MM-DD en hora de Lima (filtra scheduled_at)"),
    current: CurrentUser = Depends(require_roles("groomer")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
    pets_repo: PetRepository = Depends(get_pets_repo),
    users_repo: PostgresUserRepository = Depends(get_users_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
) -> list[GroomerOrderOut]:
    """Ruta del groomer autenticado en orden de scheduled_at, con mascota, cliente y servicio."""
    orders = await ListGroomerOrders(orders_repo=repo).execute(
        groomer_id=current.id,
        status=status_filter,
        day=day,
    )
    return [
        await _groomer_order_out(o, pets_repo=pets_repo, users_repo=users_repo, store_repo=store_repo)
        for o in orders
    ]


@router.get("/my-assignments/{id}", response_model=GroomerOrderOut)
async def get_my_assignment(
    id: UUID,
    current: CurrentUser = Depends(require_roles("groomer", "admin")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
    pets_repo: PetRepository = Depends(get_pets_repo),
    users_repo: PostgresUserRepository = Depends(get_users_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
) -> GroomerOrderOut:
    """Una parada: solo el groomer asignado (o admin). 403 si la orden no es suya."""
    order = await GetGroomerOrder(orders_repo=repo).execute(order_id=id, groomer_id=current.id, role=current.role)
    return await _groomer_order_out(order, pets_repo=pets_repo, users_repo=users_repo, store_repo=store_repo)


@router.get("/{id}", response_model=OrderOut)
async def get_order(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    order = await GetOrder(orders_repo=repo).execute(order_id=id, user_id=current.id)
    return _order_out(order)


@router.post("/{id}/status", response_model=OrderOut)
async def update_status(
    id: UUID,
    payload: UpdateStatusIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """Cambia el estado de la orden. Solo admin o el groomer asignado."""
    order = await UpdateOrderStatus(orders_repo=repo).execute(
        order_id=id,
        status=payload.status,
        actor_id=current.id,
        actor_role=current.role,
    )
    return _order_out(order)


# ------------------------------------------------------------------
# Groomer — transiciones de estado semánticas
# ------------------------------------------------------------------

@router.post("/{id}/accept", response_model=OrderOut)
async def accept_order(
    id: UUID,
    current: CurrentUser = Depends(require_roles("groomer")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """Groomer acepta el servicio asignado (reservado para flujo futuro)."""
    order = await AcceptOrder(repo=repo).execute(order_id=id, groomer_id=current.id)
    return _order_out(order)


@router.post("/{id}/depart", response_model=OrderOut)
async def depart_order(
    id: UUID,
    current: CurrentUser = Depends(require_roles("groomer")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """Groomer marcó que salió hacia el domicilio del cliente."""
    order = await DepartOrder(repo=repo).execute(order_id=id, groomer_id=current.id)
    return _order_out(order)


@router.post("/{id}/arrive", response_model=OrderOut)
async def arrive_order(
    id: UUID,
    current: CurrentUser = Depends(require_roles("groomer")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """Groomer llegó al domicilio. El servicio comienza."""
    order = await ArriveOrder(repo=repo).execute(order_id=id, groomer_id=current.id)
    return _order_out(order)


@router.post("/{id}/complete", response_model=OrderOut)
async def complete_order(
    id: UUID,
    current: CurrentUser = Depends(require_roles("groomer")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """Groomer marcó el servicio como finalizado. Exige service_step="return" (409 si no)."""
    order = await CompleteOrder(repo=repo).execute(order_id=id, groomer_id=current.id)
    return _order_out(order)


# ------------------------------------------------------------------
# Groomer — proceso del servicio (pedido 3) y fotos (pedido 6)
# ------------------------------------------------------------------

def get_photos_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresOrderPhotoRepository:
    return PostgresOrderPhotoRepository(session=session)


@router.post("/{id}/next-step", response_model=OrderOut)
async def next_step(
    id: UUID,
    payload: NextStepIn,
    current: CurrentUser = Depends(require_roles("groomer", "admin")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
    photos_repo: PostgresOrderPhotoRepository = Depends(get_photos_repo),
) -> OrderOut:
    """
    Avanza al siguiente paso: reception → bath → drying → finishing → return.
    409 si from_step no es el paso actual, si ya está en "return" (se cierra con /complete),
    si falta la foto inicial (desde reception) o si hay complementos sin realizar (desde finishing).
    """
    order = await NextServiceStep(orders_repo=repo, photos_repo=photos_repo).execute(
        order_id=id, from_step=payload.from_step, actor_id=current.id, actor_role=current.role,
    )
    return _order_out(order)


@router.post("/{id}/addons/{addon_id}/done", response_model=OrderOut)
async def addon_done(
    id: UUID,
    addon_id: str,
    current: CurrentUser = Depends(require_roles("groomer", "admin")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    """Marca un complemento comprado como realizado (idempotente). Solo en bath / drying / finishing."""
    order = await MarkAddonDone(orders_repo=repo).execute(
        order_id=id, addon_id=addon_id, actor_id=current.id, actor_role=current.role,
    )
    return _order_out(order)


def _photo_out(photo) -> OrderPhotoOut:
    from app.media.gcs import to_signed_read_url_or_none

    return OrderPhotoOut(
        id=photo.id,
        kind=photo.kind,
        read_url=to_signed_read_url_or_none(photo.object_name),
        note=photo.note,
        created_at=photo.created_at,
    )


@router.post("/{id}/photos", response_model=OrderPhotoOut, status_code=status.HTTP_201_CREATED)
async def add_photo(
    id: UUID,
    payload: OrderPhotoIn,
    current: CurrentUser = Depends(require_roles("groomer", "admin")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
    photos_repo: PostgresOrderPhotoRepository = Depends(get_photos_repo),
) -> OrderPhotoOut:
    """Registra una foto ya subida con POST /media/signed-upload (entity_type="order")."""
    photo = await AddOrderPhoto(orders_repo=repo, photos_repo=photos_repo).execute(
        order_id=id, object_name=payload.object_name, kind=payload.kind, note=payload.note,
        actor_id=current.id, actor_role=current.role,
    )
    return _photo_out(photo)


@router.get("/{id}/photos", response_model=list[OrderPhotoOut])
async def list_photos(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
    photos_repo: PostgresOrderPhotoRepository = Depends(get_photos_repo),
) -> list[OrderPhotoOut]:
    """Fotos del servicio: groomer asignado, cliente dueño o admin."""
    photos = await ListOrderPhotos(orders_repo=repo, photos_repo=photos_repo).execute(
        order_id=id, actor_id=current.id, actor_role=current.role,
    )
    return [_photo_out(p) for p in photos]


# ------------------------------------------------------------------
# Groomer — saltar parada (pedido 4) y demora (pedido 5)
# ------------------------------------------------------------------

def get_delays_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresDelayReportRepository:
    return PostgresDelayReportRepository(session=session)


@router.post("/{id}/skip", response_model=OrderOut)
async def skip_stop(
    id: UUID,
    payload: SkipIn,
    current: CurrentUser = Depends(require_roles("groomer", "admin")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
    users_repo: PostgresUserRepository = Depends(get_users_repo),
    holds_repo=Depends(get_holds_repo),
) -> OrderOut:
    """
    Salta la parada (mascota o tutor no encontrados): status=skipped. Solo en camino o recién
    llegado (in_service + reception). Notifica al cliente y a los admins; el tracking se detiene.
    El admin la reprograma con POST /admin/orders/{id}/assign (vuelve a created).
    """
    order = await SkipStop(orders_repo=repo, users_repo=users_repo, holds_repo=holds_repo).execute(
        order_id=id, reason=payload.reason, note=payload.note, actor_id=current.id, actor_role=current.role,
    )
    return _order_out(order)


def _delay_out(report) -> DelayReportOut:
    return DelayReportOut(**report.__dict__)


@router.post("/{id}/delay-report", response_model=DelayReportOut, status_code=status.HTTP_201_CREATED)
async def report_delay(
    id: UUID,
    payload: DelayReportIn,
    current: CurrentUser = Depends(require_roles("groomer", "admin")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
    delays_repo: PostgresDelayReportRepository = Depends(get_delays_repo),
    users_repo: PostgresUserRepository = Depends(get_users_repo),
) -> DelayReportOut:
    """Aviso de demora (1–180 min) antes de llegar. Notifica al cliente y a los admins."""
    report = await ReportDelay(orders_repo=repo, delays_repo=delays_repo, users_repo=users_repo).execute(
        order_id=id, delay_minutes=payload.delay_minutes, note=payload.note,
        actor_id=current.id, actor_role=current.role,
    )
    return _delay_out(report)


@router.get("/{id}/delay-reports", response_model=list[DelayReportOut])
async def list_delay_reports(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
    delays_repo: PostgresDelayReportRepository = Depends(get_delays_repo),
) -> list[DelayReportOut]:
    """Avisos de demora de la orden: groomer asignado, cliente dueño o admin."""
    reports = await ListDelayReports(orders_repo=repo, delays_repo=delays_repo).execute(
        order_id=id, actor_id=current.id, actor_role=current.role,
    )
    return [_delay_out(r) for r in reports]


# ------------------------------------------------------------------
# Admin — gestión de órdenes
# ------------------------------------------------------------------

@admin_router.get("/orders", response_model=list[OrderOut])
async def admin_list_orders(
    status_filter: Optional[OrderStatus] = Query(None, alias="status"),
    groomer_id: Optional[UUID] = Query(None),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> list[OrderOut]:
    """Lista todas las órdenes con filtros opcionales."""
    orders = await ListOrdersAdmin(orders_repo=repo).execute(status=status_filter, groomer_id=groomer_id)
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
    pets_repo: PetRepository = Depends(get_pets_repo),
) -> AssignmentOut:
    """
    Asigna un groomer a la orden y programa la fecha/hora del servicio. Notifica al cliente y al
    groomer (nueva parada, reprogramación o, al reasignar, retiro de la ruta del anterior).
    """
    order, assignment = await AssignOrder(
        orders_repo=repo,
        assignments_repo=assignments_repo,
        pets_repo=pets_repo,
    ).execute(
        order_id=id,
        groomer_id=payload.groomer_id,
        scheduled_at=payload.scheduled_at,
        assigned_by=current.id,
        notes=payload.notes,
    )
    return AssignmentOut(
        id=assignment.id,
        order_id=assignment.order_id,
        groomer_id=assignment.groomer_id,
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
    holds_repo=Depends(get_holds_repo),
    pets_repo: PetRepository = Depends(get_pets_repo),
) -> OrderOut:
    """Cancela una orden desde cualquier estado activo. Libera la reserva de cupo del día y avisa al groomer."""
    order = await CancelOrder(repo=repo, holds_repo=holds_repo, pets_repo=pets_repo).execute(order_id=id)
    return _order_out(order)


# ------------------------------------------------------------------
# Recálculo de precio por peso (orden de ajuste)
# ------------------------------------------------------------------

@router.post("/{id}/create-adjustment", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_adjustment_order(
    id: UUID,
    payload: CreateAdjustmentIn,
    current: CurrentUser = Depends(require_roles("admin", "groomer")),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
    pets_repo: PetRepository = Depends(get_pets_repo),
    store_repo: PostgresStoreRepository = Depends(get_store_repo),
) -> OrderOut:
    """
    Crea la orden de ajuste (parent_order_id={id}) por la diferencia de precio detectada
    tras registrar un peso real distinto al declarado. El precio se recalcula aquí de
    nuevo del lado del servidor (no se confía en ningún monto que mande el front) —
    requiere confirmación explícita de admin/groomer, no se genera automáticamente.
    """
    adjustment = await CreateAdjustmentOrder(
        orders_repo=repo, pets_repo=pets_repo, store_repo=store_repo,
    ).execute(order_id=id, pet_id=payload.pet_id, actor_id=current.id, actor_role=current.role)
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
    Confirma el pago en efectivo de una orden. Solo puede ejecutarlo el groomer
    asignado a esa orden, al momento de la entrega — no pasa por Culqi.
    """
    order = await ConfirmCashPayment(orders_repo=repo).execute(
        order_id=id,
        groomer_id=current.id,
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
