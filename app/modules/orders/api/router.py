from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.db import engine, get_async_session
from app.modules.orders.api.schemas import CreateOrderIn, OrderOut, PatchOrderIn, UpdateStatusIn
from app.modules.orders.app.use_cases import CreateOrderFromCart, GetOrder, ListOrders, PatchOrder, UpdateOrderStatus
from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository


router = APIRouter(tags=["orders"], prefix="/orders")


def get_orders_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresOrderRepository:
    return PostgresOrderRepository(session=session, engine=engine)


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: CreateOrderIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresOrderRepository = Depends(get_orders_repo),
) -> OrderOut:
    order = await CreateOrderFromCart(orders_repo=repo).execute(user_id=current.id, cart_id=payload.cart_id)
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
        status=payload.status
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
