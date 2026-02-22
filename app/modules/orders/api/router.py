from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.db import engine, get_async_session
from app.modules.iam.infra.postgres_user_repository import PostgresUserRepository
from app.modules.geo.infra.repository import PostgresDistrictRepository
from app.modules.orders.api.schemas import CreateOrderIn, OrderOut, PatchOrderIn, UpdateStatusIn
from app.modules.orders.app.use_cases import CreateOrderFromCart, GetOrder, ListOrders, PatchOrder, UpdateOrderStatus
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
from app.modules.cart.infra.postgres_cart_repository import PostgresCartRepository

router = APIRouter(tags=["orders"], prefix="/orders")


def get_orders_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresOrderRepository:
    return PostgresOrderRepository(session=session, engine=engine)


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: CreateOrderIn,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> OrderOut:
    # [TECH]
    # We intentionally use ONE shared AsyncSession for this entire request.
    # That way, IAM validations (address + district) and order creation share the same DB context.
    #
    # [BUSINESS]
    # Para crear una orden, el usuario debe elegir explícitamente una dirección (address_id).
    # No usamos "default" porque el usuario puede querer enviar a otra dirección.

    orders_repo = PostgresOrderRepository(session=session, engine=engine)
    cart_repo = PostgresCartRepository(session=session, engine=engine)
    iam_repo = PostgresUserRepository(session=session, engine=engine)
    geo_repo = PostgresDistrictRepository(session=session)

    # Address: explicit selection if provided; otherwise use default.
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

    # Validate district is active (service coverage)
    district = await geo_repo.get_district(addr["district_id"])
    if not district or district.get("active") is not True:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="District is not active")

    # Snapshot = "foto" de la dirección usada al crear la orden.
    # No debe cambiar aunque el usuario edite su libreta de direcciones después.
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
    return OrderOut(**order.__dict__)


@router.get("", response_model=list[OrderOut])
async def list_orders(
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> list[OrderOut]:
    orders = await ListOrders(orders_repo=repo).execute(user_id=current.id)
    return [OrderOut(**o.__dict__) for o in orders]


@router.get("/{id}", response_model=OrderOut)
async def get_order(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    order = await GetOrder(orders_repo=repo).execute(order_id=id, user_id=current.id)
    return OrderOut(**order.__dict__)


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
    return OrderOut(**order.__dict__)


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
    return OrderOut(**order.__dict__)
