from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.auth import CurrentUser, get_current_user
from app.modules.cart.api.schemas import CartItemIn, CartItemOut, CartOut, CartWithItemsOut, CheckoutOut
from app.modules.cart.app.use_cases import AddItem, Checkout, CreateCart, GetCart, ListItems, RemoveItem
from app.modules.cart.infra.cart_repository import InMemoryCartRepository


router = APIRouter(tags=["cart"], prefix="/cart")
_repo = InMemoryCartRepository()


@router.post("", response_model=CartOut, status_code=status.HTTP_201_CREATED)
async def create_cart(current: CurrentUser = Depends(get_current_user)) -> CartOut:
    cart = await CreateCart(repo=_repo).execute(user_id=current.id)
    return CartOut(**cart.__dict__)


@router.get("/{id}", response_model=CartWithItemsOut)
async def get_cart(id: UUID, current: CurrentUser = Depends(get_current_user)) -> CartWithItemsOut:
    cart = await GetCart(repo=_repo).execute(cart_id=id, user_id=current.id)
    items = await ListItems(repo=_repo).execute(cart_id=id, user_id=current.id)
    return CartWithItemsOut(
        cart=CartOut(**cart.__dict__),
        items=[CartItemOut(**i.__dict__) for i in items],
    )


@router.post("/{id}/items", response_model=CartItemOut, status_code=status.HTTP_201_CREATED)
async def add_item(id: UUID, payload: CartItemIn, current: CurrentUser = Depends(get_current_user)) -> CartItemOut:
    item = await AddItem(repo=_repo).execute(
        cart_id=id,
        user_id=current.id,
        kind=payload.kind,
        ref_id=payload.ref_id,
        name=payload.name,
        qty=payload.qty,
        unit_price=payload.unit_price,
        meta=payload.meta,
    )
    return CartItemOut(**item.__dict__)


@router.delete("/{id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(id: UUID, item_id: UUID, current: CurrentUser = Depends(get_current_user)) -> None:
    await RemoveItem(repo=_repo).execute(cart_id=id, user_id=current.id, item_id=item_id)
    return None


@router.post("/{id}/checkout", response_model=CheckoutOut)
async def checkout(id: UUID, current: CurrentUser = Depends(get_current_user)) -> CheckoutOut:
    cart = await Checkout(repo=_repo).execute(cart_id=id, user_id=current.id)
    items = await ListItems(repo=_repo).execute(cart_id=id, user_id=current.id)

    total = 0.0
    for i in items:
        if i.unit_price is not None:
            total += float(i.unit_price) * int(i.qty)

    return CheckoutOut(
        cart_id=cart.id,
        status="checked_out",
        total=total,
        currency="PEN",
        items=[CartItemOut(**i.__dict__) for i in items],
    )
