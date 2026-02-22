from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.cart.domain.cart import CartItem, CartRepository, CartSession, CartStatus


class PostgresCartRepository(CartRepository):
    def __init__(self, *, session: AsyncSession, engine: AsyncEngine) -> None:
        self._session = session
        self._engine = engine

    async def lock_cart_with_items(self, *, cart_id: UUID, user_id: UUID) -> tuple[CartSession, list[CartItem]]:
        from app.modules.cart.infra.models import CartItemModel, CartSessionModel

        stmt = (
            select(CartSessionModel)
            .where(CartSessionModel.id == cart_id, CartSessionModel.user_id == user_id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            raise ValueError("cart_not_found")

        now = datetime.now(timezone.utc)
        if row.status == CartStatus.active and now > row.expires_at:
            stmt_update = (
                update(CartSessionModel)
                .where(CartSessionModel.id == cart_id)
                .values(status=CartStatus.expired, updated_at=now)
                .returning(CartSessionModel)
            )
            result_update = await self._session.execute(stmt_update)
            row = result_update.scalar_one()

        if row.status in {CartStatus.expired, CartStatus.cancelled}:
            raise ValueError("cart_not_active")

        items_stmt = select(CartItemModel).where(CartItemModel.cart_id == cart_id).order_by(CartItemModel.created_at.asc())
        items_result = await self._session.execute(items_stmt)
        item_rows = items_result.scalars().all()

        cart = CartSession(
            id=row.id,
            user_id=row.user_id,
            status=row.status,
            expires_at=row.expires_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        items = [
            CartItem(
                id=irow.id,
                cart_id=irow.cart_id,
                kind=irow.kind,
                ref_id=irow.ref_id,
                name=irow.name,
                qty=irow.qty,
                unit_price=float(irow.unit_price) if irow.unit_price is not None else None,
                meta=irow.meta,
            )
            for irow in item_rows
        ]
        return cart, items

    async def create_cart(self, user_id: UUID) -> CartSession:
        cart = CartSession.new(user_id=user_id, ttl_hours=2)
        from app.modules.cart.infra.models import CartSessionModel

        model = CartSessionModel(
            id=cart.id,
            user_id=cart.user_id,
            status=cart.status,
            expires_at=cart.expires_at,
            created_at=cart.created_at,
            updated_at=cart.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return cart

    async def _apply_expiration(self, cart_id: UUID, user_id: UUID) -> CartSession:
        from app.modules.cart.infra.models import CartSessionModel

        stmt = select(CartSessionModel).where(
            CartSessionModel.id == cart_id, CartSessionModel.user_id == user_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            raise ValueError("cart_not_found")

        now = datetime.now(timezone.utc)
        if row.status == CartStatus.active and now > row.expires_at:
            stmt_update = (
                update(CartSessionModel)
                .where(CartSessionModel.id == cart_id)
                .values(status=CartStatus.expired, updated_at=now)
                .returning(CartSessionModel)
            )
            result_update = await self._session.execute(stmt_update)
            row = result_update.scalar_one()

        return CartSession(
            id=row.id,
            user_id=row.user_id,
            status=row.status,
            expires_at=row.expires_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_cart(self, cart_id: UUID, user_id: UUID) -> CartSession:
        return await self._apply_expiration(cart_id, user_id)

    async def get_active_cart_for_user(self, user_id: UUID) -> Optional[CartSession]:
        """
        Obtiene el carrito activo más reciente del usuario.
        Retorna None si no tiene carrito activo o si expiró.
        """
        from app.modules.cart.infra.models import CartSessionModel

        stmt = (
            select(CartSessionModel)
            .where(
                CartSessionModel.user_id == user_id,
                CartSessionModel.status == CartStatus.active
            )
            .order_by(CartSessionModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()

        if not row:
            return None

        # Verificar si expiró
        now = datetime.now(timezone.utc)
        if now > row.expires_at:
            # Marcar como expirado
            stmt_update = (
                update(CartSessionModel)
                .where(CartSessionModel.id == row.id)
                .values(status=CartStatus.expired, updated_at=now)
            )
            await self._session.execute(stmt_update)
            return None

        return CartSession(
            id=row.id,
            user_id=row.user_id,
            status=row.status,
            expires_at=row.expires_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def add_item(self, cart_id: UUID, user_id: UUID, item: CartItem) -> CartItem:
        cart = await self.get_cart(cart_id, user_id)
        if cart.status != CartStatus.active:
            raise ValueError("cart_not_active")
        if item.cart_id != cart_id:
            raise ValueError("invalid_cart_item")

        from app.modules.cart.infra.models import CartItemModel

        kind_value = getattr(getattr(item, "kind", None), "value", getattr(item, "kind", None))

        model = CartItemModel(
            id=item.id,
            cart_id=item.cart_id,
            kind=str(kind_value),
            ref_id=str(item.ref_id),
            name=item.name,
            qty=item.qty,
            unit_price=item.unit_price,
            meta=item.meta,
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()

        # Update cart updated_at
        await self._touch_cart(cart_id)

        return item

    async def add_items(self, cart_id: UUID, user_id: UUID, items: list[CartItem]) -> list[CartItem]:
        """
        Agrega múltiples items al carrito de una vez.
        """
        cart = await self.get_cart(cart_id, user_id)
        if cart.status != CartStatus.active:
            raise ValueError("cart_not_active")

        from app.modules.cart.infra.models import CartItemModel

        models = []
        for item in items:
            if item.cart_id != cart_id:
                raise ValueError("invalid_cart_item")

            kind_value = getattr(getattr(item, "kind", None), "value", getattr(item, "kind", None))

            model = CartItemModel(
                id=item.id,
                cart_id=item.cart_id,
                kind=str(kind_value),
                ref_id=str(item.ref_id),
                name=item.name,
                qty=item.qty,
                unit_price=item.unit_price,
                meta=item.meta,
                created_at=datetime.now(timezone.utc),
            )
            models.append(model)

        self._session.add_all(models)
        await self._session.flush()
        await self._session.commit()

        # Update cart updated_at
        await self._touch_cart(cart_id)

        return items

    async def replace_all_items(self, cart_id: UUID, user_id: UUID, items: list[CartItem]) -> list[CartItem]:
        """
        Reemplaza todos los items del carrito.
        Útil para cambiar de servicio base.
        """
        cart = await self.get_cart(cart_id, user_id)
        if cart.status != CartStatus.active:
            raise ValueError("cart_not_active")

        from app.modules.cart.infra.models import CartItemModel

        # Eliminar todos los items actuales
        stmt = delete(CartItemModel).where(CartItemModel.cart_id == cart_id)
        await self._session.execute(stmt)

        # Agregar los nuevos items
        models = []
        for item in items:
            if item.cart_id != cart_id:
                raise ValueError("invalid_cart_item")

            kind_value = getattr(getattr(item, "kind", None), "value", getattr(item, "kind", None))

            model = CartItemModel(
                id=item.id,
                cart_id=item.cart_id,
                kind=str(kind_value),
                ref_id=str(item.ref_id),
                name=item.name,
                qty=item.qty,
                unit_price=item.unit_price,
                meta=item.meta,
                created_at=datetime.now(timezone.utc),
            )
            models.append(model)

        self._session.add_all(models)
        await self._session.flush()
        await self._session.commit()

        # Update cart updated_at
        await self._touch_cart(cart_id)

        return items

    async def remove_item(self, cart_id: UUID, user_id: UUID, item_id: UUID) -> None:
        cart = await self.get_cart(cart_id, user_id)
        if cart.status != CartStatus.active:
            raise ValueError("cart_not_active")

        from app.modules.cart.infra.models import CartItemModel

        stmt = delete(CartItemModel).where(
            CartItemModel.id == item_id, CartItemModel.cart_id == cart_id
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            raise ValueError("item_not_found")

        await self._session.commit()
        await self._touch_cart(cart_id)

    async def list_items(self, cart_id: UUID, user_id: UUID) -> list[CartItem]:
        _ = await self.get_cart(cart_id, user_id)  # validates ownership and expiration

        from app.modules.cart.infra.models import CartItemModel

        stmt = select(CartItemModel).where(CartItemModel.cart_id == cart_id).order_by(
            CartItemModel.created_at.asc()
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            CartItem(
                id=row.id,
                cart_id=row.cart_id,
                kind=row.kind,
                ref_id=row.ref_id,
                name=row.name,
                qty=row.qty,
                unit_price=float(row.unit_price) if row.unit_price is not None else None,
                meta=row.meta,
            )
            for row in rows
        ]

    async def checkout(self, cart_id: UUID, user_id: UUID) -> CartSession:
        cart = await self.get_cart(cart_id, user_id)
        if cart.status != CartStatus.active:
            raise ValueError("cart_not_active")

        from app.modules.cart.infra.models import CartSessionModel

        stmt = (
            update(CartSessionModel)
            .where(CartSessionModel.id == cart_id)
            .values(status=CartStatus.checked_out, updated_at=datetime.now(timezone.utc))
            .returning(CartSessionModel)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one()
        await self._session.commit()
        return CartSession(
            id=row.id,
            user_id=row.user_id,
            status=row.status,
            expires_at=row.expires_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def _touch_cart(self, cart_id: UUID) -> None:
        from app.modules.cart.infra.models import CartSessionModel

        stmt = (
            update(CartSessionModel)
            .where(CartSessionModel.id == cart_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        await self._session.execute(stmt)

    async def expire_carts(self, *, now: datetime) -> int:
        from app.modules.cart.infra.models import CartSessionModel

        stmt = (
            update(CartSessionModel)
            .where(CartSessionModel.status == CartStatus.active, CartSessionModel.expires_at < now)
            .values(status=CartStatus.expired, updated_at=now)
        )
        res = await self._session.execute(stmt)
        await self._session.commit()
        return int(res.rowcount or 0)
