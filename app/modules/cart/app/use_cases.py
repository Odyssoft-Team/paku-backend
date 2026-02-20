from dataclasses import dataclass
from typing import Any, Optional, Union
from uuid import UUID
from datetime import datetime

from fastapi import HTTPException, status

from app.modules.cart.domain.cart import CartItem, CartItemKind, CartRepository, CartSession, CartStatus


def _validate_date_format(date_str: str, field_name: str) -> None:
    """Valida que la fecha tenga formato YYYY-MM-DD"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format. Expected YYYY-MM-DD, got '{date_str}'"
        )


def _validate_time_format(time_str: str, field_name: str) -> None:
    """Valida que la hora tenga formato HH:MM"""
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format. Expected HH:MM, got '{time_str}'"
        )


def _raise_cart_error(code: str) -> None:
    if code == "cart_not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    if code == "cart_not_active":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart is not active (expired/checked out/cancelled)")
    if code == "item_not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if code == "invalid_cart_item":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cart item")
    if code == "multiple_base_services":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot have multiple base services in cart")


def _validate_single_base_service(items: list[dict[str, Any]]) -> None:
    """
    Valida que solo haya un servicio base en la lista de items.
    Regla de negocio: 1 carrito = 1 servicio base + opcionales addons.
    """
    base_count = sum(1 for item in items if item.get("kind") == CartItemKind.service_base or item.get("kind") == "service_base")
    if base_count > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot have multiple base services in cart. Only 1 base service + addons allowed."
        )
    if base_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cart must have at least one base service"
        )


def _validate_required_meta_fields(items: list[dict[str, Any]]) -> None:
    """
    Valida que los servicios base tengan los campos requeridos en meta.
    
    Campos obligatorios:
    - pet_id: UUID de la mascota
    - scheduled_date: Fecha programada (YYYY-MM-DD)
    - scheduled_time: Hora programada (HH:MM)
    """
    for item in items:
        if item.get("kind") in (CartItemKind.service_base, "service_base"):
            meta = item.get("meta", {})
            
            # Validar pet_id
            if not meta.get("pet_id"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Service '{item.get('name', 'unknown')}' requires 'pet_id' in meta"
                )
            
            # Validar scheduled_date
            scheduled_date = meta.get("scheduled_date")
            if not scheduled_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Service '{item.get('name', 'unknown')}' requires 'scheduled_date' in meta (format: YYYY-MM-DD)"
                )
            _validate_date_format(str(scheduled_date), "scheduled_date")
            
            # Validar scheduled_time
            scheduled_time = meta.get("scheduled_time")
            if not scheduled_time:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Service '{item.get('name', 'unknown')}' requires 'scheduled_time' in meta (format: HH:MM)"
                )
            _validate_time_format(str(scheduled_time), "scheduled_time")


def _validate_addon_dependencies(items: list[dict[str, Any]]) -> None:
    """
    Valida que los addons referencien correctamente al servicio base.
    
    Regla de negocio:
    - Los addons deben tener en meta.requires_base el ref_id del servicio base
    - O pueden no tener este campo (se asume que aplican al servicio base del carrito)
    """
    # Obtener el ref_id del servicio base
    base_service = next(
        (item for item in items if item.get("kind") in (CartItemKind.service_base, "service_base")),
        None
    )
    
    if not base_service:
        return  # Ya validado en _validate_single_base_service
    
    base_ref_id = str(base_service.get("ref_id"))
    
    # Validar addons
    for item in items:
        if item.get("kind") in (CartItemKind.service_addon, "service_addon"):
            meta = item.get("meta", {})
            requires_base = meta.get("requires_base")
            
            # Si especifica requires_base, debe coincidir con el servicio base
            if requires_base and str(requires_base) != base_ref_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Addon '{item.get('name', 'unknown')}' requires base service '{requires_base}', "
                           f"but cart has '{base_ref_id}'"
                )


@dataclass
class CreateCart:
    repo: CartRepository

    async def execute(self, *, user_id: UUID) -> CartSession:
        return self.repo.create_cart(user_id=user_id)


@dataclass
class GetCart:
    repo: CartRepository

    async def execute(self, *, cart_id: UUID, user_id: UUID) -> CartSession:
        try:
            cart = self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")
        return cart


@dataclass
class GetOrCreateActiveCart:
    repo: CartRepository

    async def execute(self, *, user_id: UUID) -> CartSession:
        """
        Obtiene el carrito activo del usuario, o crea uno nuevo si no existe.
        Útil para recuperar el carrito al abrir la app desde cualquier dispositivo.
        """
        cart = await self.repo.get_active_cart_for_user(user_id=user_id)
        
        if cart is None:
            # No tiene carrito activo (o expiró), crear uno nuevo
            cart = await self.repo.create_cart(user_id=user_id)
        
        return cart


@dataclass
class CreateCartWithItems:
    repo: CartRepository

    async def execute(
        self,
        *,
        user_id: UUID,
        items: list[dict[str, Any]],
    ) -> tuple[CartSession, list[CartItem]]:
        """
        Crea un carrito nuevo con items en un solo paso.
        Valida que solo haya 1 servicio base.
        """
        # Validaciones de negocio
        _validate_single_base_service(items)
        _validate_required_meta_fields(items)
        _validate_addon_dependencies(items)
        
        # Crear carrito
        cart = await self.repo.create_cart(user_id=user_id)
        
        # Crear items
        cart_items = [
            CartItem.new(
                cart_id=cart.id,
                kind=item["kind"],
                ref_id=item["ref_id"],
                name=item.get("name"),
                qty=item.get("qty", 1),
                unit_price=item.get("unit_price"),
                meta=item.get("meta"),
            )
            for item in items
        ]
        
        try:
            added_items = await self.repo.add_items(cart_id=cart.id, user_id=user_id, items=cart_items)
            return cart, added_items
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


@dataclass
class AddItem:
    repo: CartRepository

    async def execute(
        self,
        *,
        cart_id: UUID,
        user_id: UUID,
        kind: CartItemKind,
        ref_id: Union[UUID, str],
        name: Optional[str] = None,
        qty: int = 1,
        unit_price: Optional[float] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> CartItem:
        try:
            cart = self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        item = CartItem.new(
            cart_id=cart_id,
            kind=kind,
            ref_id=ref_id,
            name=name,
            qty=qty,
            unit_price=unit_price,
            meta=meta,
        )
        try:
            return self.repo.add_item(cart_id=cart_id, user_id=user_id, item=item)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


@dataclass
class RemoveItem:
    repo: CartRepository

    async def execute(self, *, cart_id: UUID, user_id: UUID, item_id: UUID) -> None:
        try:
            cart = self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        try:
            self.repo.remove_item(cart_id=cart_id, user_id=user_id, item_id=item_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


@dataclass
class ListItems:
    repo: CartRepository

    async def execute(self, *, cart_id: UUID, user_id: UUID) -> list[CartItem]:
        try:
            cart = self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        return self.repo.list_items(cart_id=cart_id, user_id=user_id)


@dataclass
class Checkout:
    repo: CartRepository

    async def execute(self, *, cart_id: UUID, user_id: UUID) -> CartSession:
        try:
            cart = self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        try:
            return self.repo.checkout(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


@dataclass
class AddItemsBatch:
    repo: CartRepository

    async def execute(
        self,
        *,
        cart_id: UUID,
        user_id: UUID,
        items: list[dict[str, Any]],
    ) -> list[CartItem]:
        try:
            cart = self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        # Validaciones de negocio
        _validate_single_base_service(items)
        _validate_required_meta_fields(items)
        _validate_addon_dependencies(items)

        cart_items = [
            CartItem.new(
                cart_id=cart_id,
                kind=item["kind"],
                ref_id=item["ref_id"],
                name=item.get("name"),
                qty=item.get("qty", 1),
                unit_price=item.get("unit_price"),
                meta=item.get("meta"),
            )
            for item in items
        ]

        try:
            return self.repo.add_items(cart_id=cart_id, user_id=user_id, items=cart_items)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


@dataclass
class ReplaceAllItems:
    repo: CartRepository

    async def execute(
        self,
        *,
        cart_id: UUID,
        user_id: UUID,
        items: list[dict[str, Any]],
    ) -> list[CartItem]:
        try:
            cart = self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise

        if cart.status == CartStatus.expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Cart expired")

        # Validaciones de negocio
        _validate_single_base_service(items)
        _validate_required_meta_fields(items)
        _validate_addon_dependencies(items)

        cart_items = [
            CartItem.new(
                cart_id=cart_id,
                kind=item["kind"],
                ref_id=item["ref_id"],
                name=item.get("name"),
                qty=item.get("qty", 1),
                unit_price=item.get("unit_price"),
                meta=item.get("meta"),
            )
            for item in items
        ]

        try:
            return self.repo.replace_all_items(cart_id=cart_id, user_id=user_id, items=cart_items)
        except ValueError as exc:
            _raise_cart_error(str(exc))
            raise


@dataclass
class ValidateCart:
    repo: CartRepository

    async def execute(self, *, cart_id: UUID, user_id: UUID) -> dict[str, Any]:
        """
        Valida el carrito antes del checkout.
        
        Verificaciones:
        1. Carrito existe y está activo
        2. Tiene al menos 1 item (servicio base)
        3. Items tienen precios válidos
        4. Meta tiene campos requeridos
        5. Addons referencian correctamente al servicio base
        
        Retorna:
        - valid: bool
        - errors: list[str] (si hay errores)
        - warnings: list[str] (advertencias no bloqueantes)
        - total: float (total calculado)
        """
        errors = []
        warnings = []
        
        # 1. Validar carrito
        try:
            cart = self.repo.get_cart(cart_id=cart_id, user_id=user_id)
        except ValueError as exc:
            return {
                "valid": False,
                "errors": [f"Cart error: {str(exc)}"],
                "warnings": [],
                "total": 0.0
            }
        
        if cart.status == CartStatus.expired:
            return {
                "valid": False,
                "errors": ["Cart has expired"],
                "warnings": [],
                "total": 0.0
            }
        
        # 2. Validar items
        items = self.repo.list_items(cart_id=cart_id, user_id=user_id)
        
        if not items:
            return {
                "valid": False,
                "errors": ["Cart is empty. Add at least one service."],
                "warnings": [],
                "total": 0.0
            }
        
        # 3. Validar servicio base
        base_services = [i for i in items if i.kind == CartItemKind.service_base]
        
        if not base_services:
            errors.append("Cart must have at least one base service")
        elif len(base_services) > 1:
            errors.append(f"Cart has {len(base_services)} base services, only 1 allowed")
        
        # 4. Validar precios
        total = 0.0
        for item in items:
            if item.unit_price is None or item.unit_price <= 0:
                errors.append(f"Item '{item.name or item.ref_id}' has invalid price")
            else:
                total += float(item.unit_price) * int(item.qty)
        
        # 5. Validar meta requeridos
        for item in items:
            if item.kind == CartItemKind.service_base:
                meta = item.meta or {}
                
                if not meta.get("pet_id"):
                    errors.append(f"Service '{item.name}' missing required field: pet_id")
                
                if not meta.get("scheduled_date"):
                    errors.append(f"Service '{item.name}' missing required field: scheduled_date")
                
                if not meta.get("scheduled_time"):
                    errors.append(f"Service '{item.name}' missing required field: scheduled_time")
        
        # 6. Validar addons
        if base_services:
            base_ref_id = str(base_services[0].ref_id)
            
            for item in items:
                if item.kind == CartItemKind.service_addon:
                    meta = item.meta or {}
                    requires_base = meta.get("requires_base")
                    
                    if requires_base and str(requires_base) != base_ref_id:
                        errors.append(
                            f"Addon '{item.name}' requires base service '{requires_base}', "
                            f"but cart has '{base_ref_id}'"
                        )
        
        # 7. Advertencias (no bloqueantes)
        if total == 0:
            warnings.append("Total is 0. Please verify prices.")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total": total
        }
