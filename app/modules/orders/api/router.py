from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import CurrentUser, get_current_user
from app.modules.orders.api.schemas import CreateOrderIn, OrderOut, UpdateStatusIn
from app.modules.orders.app.use_cases import CreateOrderFromCart, GetOrder, ListOrders, UpdateOrderStatus
from app.modules.orders.infra.order_repository import InMemoryOrderRepository


router = APIRouter(tags=["orders"], prefix="/orders")
_repo = InMemoryOrderRepository()


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(payload: CreateOrderIn, current: CurrentUser = Depends(get_current_user)) -> OrderOut:
    order = await CreateOrderFromCart(orders_repo=_repo).execute(user_id=current.id, cart_id=payload.cart_id)
    return OrderOut(**order.__dict__)


@router.get("", response_model=list[OrderOut])
async def list_orders(current: CurrentUser = Depends(get_current_user)) -> list[OrderOut]:
    orders = await ListOrders(orders_repo=_repo).execute(user_id=current.id)
    return [OrderOut(**o.__dict__) for o in orders]


@router.get("/{id}", response_model=OrderOut)
async def get_order(id: UUID, current: CurrentUser = Depends(get_current_user)) -> OrderOut:
    order = await GetOrder(orders_repo=_repo).execute(order_id=id, user_id=current.id)
    return OrderOut(**order.__dict__)


@router.post("/{id}/status", response_model=OrderOut)
async def update_status(id: UUID, payload: UpdateStatusIn, current: CurrentUser = Depends(get_current_user)) -> OrderOut:
    if current.role not in {"admin", "ally"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    order = await UpdateOrderStatus(orders_repo=_repo).execute(order_id=id, status=payload.status)
    return OrderOut(**order.__dict__)
