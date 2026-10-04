from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.db import engine, get_async_session
from app.modules.cart.api.schemas import CartItemIn, CartItemsBatchIn, CartItemOut, CartOut, CartWithItemsOut, CheckoutOut, CartValidationOut
from app.modules.cart.app.use_cases import (
    AddItem,
    CartPricing,
    Checkout,
    CreateCart,
    CreateCartWithItems,
    GetCart,
    GetOrCreateActiveCart,
    ListItems,
    RemoveItem,
    ReplaceAllItems,
    ValidateCart,
)
from app.modules.cart.app.use_cases_impl.hold_binding import CartHolds
from app.modules.cart.app.use_cases_impl.pricing import prices_differ
from app.modules.cart.infra.postgres_cart_repository import PostgresCartRepository


router = APIRouter(tags=["cart"], prefix="/cart")


def get_cart_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresCartRepository:
    return PostgresCartRepository(session=session, engine=engine)


def get_cart_pricing(session: AsyncSession = Depends(get_async_session)) -> CartPricing:
    from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository
    from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository

    return CartPricing(
        store_repo=PostgresStoreRepository(session=session, engine=engine),
        pets_repo=PostgresPetRepository(session=session, engine=engine),
    )


def get_cart_holds(session: AsyncSession = Depends(get_async_session)) -> CartHolds:
    from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository

    return CartHolds(hold_repo=PostgresHoldRepository(session=session, engine=engine))


def _item_out(item, client_unit_price: Optional[float] = None) -> CartItemOut:
    """El precio es siempre el del servidor; si el front mandó otro, se marca price_adjusted."""
    out = CartItemOut(**item.__dict__)
    if client_unit_price is not None and prices_differ(client_unit_price, item.unit_price):
        out.price_adjusted = True
        out.client_unit_price = client_unit_price
    return out


@router.get("", response_model=CartWithItemsOut)
async def get_active_cart(
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresCartRepository = Depends(get_cart_repo),
) -> CartWithItemsOut:
    """
    Obtiene el carrito activo del usuario (o crea uno nuevo si no existe).
    
    Útil para:
    - Abrir la app y recuperar el carrito desde cualquier dispositivo
    - No perder el carrito si el usuario cierra/desinstala la app
    - Continuar comprando desde donde dejó
    
    Si el carrito expiró (>2 horas), se crea uno nuevo automáticamente.
    """
    cart = await GetOrCreateActiveCart(repo=repo).execute(user_id=current.id)
    items = await ListItems(repo=repo).execute(cart_id=cart.id, user_id=current.id)
    return CartWithItemsOut(
        cart=CartOut(**cart.__dict__),
        items=[CartItemOut(**i.__dict__) for i in items],
    )


@router.post("/items", response_model=CartWithItemsOut, status_code=status.HTTP_201_CREATED)
async def create_cart_with_items(
    payload: CartItemsBatchIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresCartRepository = Depends(get_cart_repo),
    pricing: CartPricing = Depends(get_cart_pricing),
    holds: CartHolds = Depends(get_cart_holds),
) -> CartWithItemsOut:
    """
    Crea un carrito nuevo con múltiples items de una vez.

    El servicio base debe traer meta.hold_id (reserva de cupo hecha antes con POST /holds); la fecha
    del servicio sale de la reserva, que desde ahora vence junto con el carrito.

    Precios y nombres los calcula el backend (store) por especie, raza y peso de la mascota;
    el unit_price que envíe el front se ignora (price_adjusted=true si no coincidía).
    
    Flujo típico:
    1. Usuario selecciona mascota
    2. Usuario selecciona servicio base + addons opcionales
    3. Frontend llama a este endpoint con todos los items
    
    Validaciones:
    - Solo 1 servicio base por carrito
    - Addons opcionales (0 o más)
    
    Retorna el carrito creado + items agregados.
    """
    items_dict = [item.model_dump() for item in payload.items]
    cart, items = await CreateCartWithItems(repo=repo, pricing=pricing, holds=holds).execute(
        user_id=current.id,
        items=items_dict,
    )
    return CartWithItemsOut(
        cart=CartOut(**cart.__dict__),
        items=[_item_out(i, sent.unit_price) for i, sent in zip(items, payload.items)],
    )


@router.get("/{id}", response_model=CartWithItemsOut)
async def get_cart(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresCartRepository = Depends(get_cart_repo),
) -> CartWithItemsOut:
    cart = await GetCart(repo=repo).execute(cart_id=id, user_id=current.id)
    items = await ListItems(repo=repo).execute(cart_id=id, user_id=current.id)
    return CartWithItemsOut(
        cart=CartOut(**cart.__dict__),
        items=[CartItemOut(**i.__dict__) for i in items],
    )


@router.post("/{id}/items", response_model=CartItemOut, status_code=status.HTTP_201_CREATED)
async def add_item(
    id: UUID,
    payload: CartItemIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresCartRepository = Depends(get_cart_repo),
    pricing: CartPricing = Depends(get_cart_pricing),
    holds: CartHolds = Depends(get_cart_holds),
) -> CartItemOut:
    """
    Agrega un item individual al carrito existente.
    
    Uso típico: Agregar addons adicionales después de crear el carrito.
    
    DEPRECADO: Preferir usar POST /cart/items (batch) o PUT /cart/{id}/items (replace).
    """
    item = await AddItem(repo=repo, pricing=pricing, holds=holds).execute(
        cart_id=id,
        user_id=current.id,
        kind=payload.kind,
        ref_id=payload.ref_id,
        name=payload.name,
        qty=payload.qty,
        unit_price=payload.unit_price,
        meta=payload.meta,
    )
    return _item_out(item, payload.unit_price)


@router.put("/{id}/items", response_model=CartWithItemsOut)
async def replace_all_items(
    id: UUID,
    payload: CartItemsBatchIn,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresCartRepository = Depends(get_cart_repo),
    pricing: CartPricing = Depends(get_cart_pricing),
    holds: CartHolds = Depends(get_cart_holds),
) -> CartWithItemsOut:
    """
    Reemplaza TODOS los items del carrito (precios calculados por el backend). Si cambia la reserva
    del servicio base, la anterior se libera.
    
    Uso típico: Usuario quiere cambiar de servicio base.
    
    Ejemplo:
    - Tenía: Clásico + Corte de uñas
    - Quiere: Premium + Corte de uñas + Limpieza dental
    
    Validaciones:
    - Solo 1 servicio base por carrito
    - Addons opcionales (0 o más)
    
    Retorna el carrito actualizado + nuevos items.
    """
    items_dict = [item.model_dump() for item in payload.items]
    items = await ReplaceAllItems(repo=repo, pricing=pricing, holds=holds).execute(
        cart_id=id,
        user_id=current.id,
        items=items_dict,
    )
    cart = await GetCart(repo=repo).execute(cart_id=id, user_id=current.id)
    return CartWithItemsOut(
        cart=CartOut(**cart.__dict__),
        items=[_item_out(i, sent.unit_price) for i, sent in zip(items, payload.items)],
    )


@router.delete("/{id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(
    id: UUID,
    item_id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresCartRepository = Depends(get_cart_repo),
    holds: CartHolds = Depends(get_cart_holds),
) -> None:
    """Quita un ítem. Si es el servicio base, su reserva de cupo se libera."""
    await RemoveItem(repo=repo, holds=holds).execute(cart_id=id, user_id=current.id, item_id=item_id)
    return None


@router.post("/{id}/validate", response_model=CartValidationOut)
async def validate_cart(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresCartRepository = Depends(get_cart_repo),
) -> CartValidationOut:
    """
    Valida el carrito antes del checkout.
    
    Verificaciones:
    - Carrito existe y está activo
    - Tiene al menos 1 servicio base
    - Items tienen precios válidos
    - Meta contiene campos requeridos (pet_id, scheduled_date, scheduled_time)
    - Addons referencian correctamente al servicio base
    
    Útil para:
    - Mostrar errores antes de intentar checkout
    - Validar datos en frontend antes de enviar
    - Debug de problemas en carrito
    
    Retorna:
    - valid: true/false
    - errors: lista de errores bloqueantes
    - warnings: lista de advertencias no bloqueantes
    - total: total calculado
    """
    result = await ValidateCart(repo=repo).execute(cart_id=id, user_id=current.id)
    return CartValidationOut(
        valid=result["valid"],
        errors=result["errors"],
        warnings=result["warnings"],
        total=result["total"],
        currency="PEN"
    )


@router.post("/{id}/checkout", response_model=CheckoutOut)
async def checkout(
    id: UUID,
    current: CurrentUser = Depends(get_current_user),
    repo: PostgresCartRepository = Depends(get_cart_repo),
    pricing: CartPricing = Depends(get_cart_pricing),
    holds: CartHolds = Depends(get_cart_holds),
) -> CheckoutOut:
    """
    Finaliza el carrito marcándolo como checked_out.

    Antes de cerrar, el backend recotiza el carrito. Si algún precio cambió desde que se agregó
    (regla de precio o peso de la mascota), guarda los precios nuevos y responde
    409 {"code": "PRICE_CHANGED", "items": [...], "total": ...}; el front muestra el nuevo
    total y vuelve a llamar a checkout.

    Nota: la creación de la orden (tabla `orders`) se realiza vía POST /orders,
    porque requiere seleccionar una dirección (address_id o default).
    
    IMPORTANTE: Valida automáticamente el carrito antes de procesar.
    Si hay errores, retorna 400 con la lista de problemas.
    
    Validaciones automáticas:
    - Carrito activo con items
    - Servicio base presente
    - Precios válidos
    - Meta completa (pet_id, scheduled_date, scheduled_time)
    - Addons correctamente referenciados
    
    Flujo:
    1. Valida carrito
    2. Si válido: marca como checked_out y retorna resumen
    3. Si inválido: retorna errores sin procesar
    """
    # Validar antes de procesar
    validation = await ValidateCart(repo=repo).execute(cart_id=id, user_id=current.id)
    
    if not validation["valid"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Cart validation failed",
                "errors": validation["errors"],
                "warnings": validation["warnings"]
            }
        )
    
    # Procesar checkout
    cart = await Checkout(repo=repo, pricing=pricing, holds=holds).execute(cart_id=id, user_id=current.id)
    items = await ListItems(repo=repo).execute(cart_id=id, user_id=current.id)

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
