from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.campaigns.domain.campaigns import Campaign
from app.modules.campaigns.infra.models import CampaignModel, CampaignRedemptionModel, utcnow
from app.modules.cart.domain.cart import CART_TTL_HOURS
from app.modules.orders.infra.models import OrderModel


def _to_campaign(m: CampaignModel) -> Campaign:
    return Campaign(
        id=m.id, code=m.code, name=m.name, objective=m.objective, audience=m.audience, benefit_type=m.benefit_type,
        value=float(m.value or 0), addon_code=m.addon_code, channels=list(m.channels or []), starts_on=m.starts_on,
        ends_on=m.ends_on, status=m.status, automatic=bool(m.automatic), max_uses_per_customer=m.max_uses_per_customer,
        max_total_uses=m.max_total_uses, created_at=m.created_at, updated_at=m.updated_at, created_by=m.created_by,
    )


def _counting_uses():
    """Un uso cuenta mientras la orden esté pagada o en verificación, o siga pendiente dentro de la vida del
    carrito (una orden abandonada sin pagar no le quema el cupón al cliente). Las canceladas se liberan."""
    recent = datetime.now(timezone.utc) - timedelta(hours=CART_TTL_HOURS)
    return and_(
        CampaignRedemptionModel.released_at.is_(None),
        OrderModel.status != "cancelled",
        or_(
            OrderModel.payment_status.in_(("paid", "verifying")),
            and_(OrderModel.payment_status == "pending", OrderModel.created_at >= recent),
        ),
    )


class PostgresCampaignRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Campañas
    # ------------------------------------------------------------------

    async def list_campaigns(self) -> list[Campaign]:
        stmt = select(CampaignModel).order_by(CampaignModel.starts_on.desc(), CampaignModel.code)
        return [_to_campaign(m) for m in (await self._session.execute(stmt)).scalars().all()]

    async def get(self, campaign_id: UUID) -> Optional[Campaign]:
        m = await self._session.get(CampaignModel, campaign_id)
        return _to_campaign(m) if m else None

    async def get_by_code(self, code: str) -> Optional[Campaign]:
        m = (await self._session.execute(select(CampaignModel).where(CampaignModel.code == code))).scalars().first()
        return _to_campaign(m) if m else None

    async def save(self, fields: dict, *, campaign_id: Optional[UUID] = None, actor_id: Optional[UUID] = None) -> Campaign:
        """Crea (sin `campaign_id`) o actualiza. ValueError("code_taken") si el código ya existe."""
        now = utcnow()
        if campaign_id is None:
            m = CampaignModel(created_by=actor_id, created_at=now)
            self._session.add(m)
        else:
            m = await self._session.get(CampaignModel, campaign_id)
            if m is None:
                raise ValueError("campaign_not_found")
        for key, value in fields.items():
            setattr(m, key, Decimal(str(value)) if key == "value" else value)
        m.updated_at = now
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise ValueError("code_taken")
        await self._session.refresh(m)
        return _to_campaign(m)

    # ------------------------------------------------------------------
    # Usos
    # ------------------------------------------------------------------

    async def uses(self, campaign_ids: list[UUID], *, user_id: Optional[UUID] = None) -> dict[UUID, int]:
        if not campaign_ids:
            return {}
        stmt = (
            select(CampaignRedemptionModel.campaign_id, func.count())
            .join(OrderModel, OrderModel.id == CampaignRedemptionModel.order_id)
            .where(CampaignRedemptionModel.campaign_id.in_(campaign_ids), _counting_uses())
            .group_by(CampaignRedemptionModel.campaign_id)
        )
        if user_id is not None:
            stmt = stmt.where(CampaignRedemptionModel.user_id == user_id)
        return {cid: int(n) for cid, n in (await self._session.execute(stmt)).all()}

    async def add_redemption(self, *, campaign_id: UUID, order_id: UUID, user_id: UUID, discount: float) -> None:
        self._session.add(CampaignRedemptionModel(
            campaign_id=campaign_id, order_id=order_id, user_id=user_id, discount_amount=Decimal(str(discount)),
        ))
        await self._session.commit()

    async def release_for_order(self, order_id: UUID) -> bool:
        """Libera el uso de la orden (al cancelarla). True si había uno."""
        stmt = select(CampaignRedemptionModel).where(
            CampaignRedemptionModel.order_id == order_id, CampaignRedemptionModel.released_at.is_(None)
        )
        m = (await self._session.execute(stmt)).scalars().first()
        if m is None:
            return False
        m.released_at = utcnow()
        await self._session.commit()
        return True

    async def results(self, campaign_ids: list[UUID]) -> dict[UUID, tuple[int, float, float]]:
        """Por campaña, solo órdenes pagadas: (usos, descuento otorgado, ventas con la campaña)."""
        if not campaign_ids:
            return {}
        stmt = (
            select(
                CampaignRedemptionModel.campaign_id, func.count(),
                func.coalesce(func.sum(CampaignRedemptionModel.discount_amount), 0),
                func.coalesce(func.sum(OrderModel.total_snapshot), 0),
            )
            .join(OrderModel, OrderModel.id == CampaignRedemptionModel.order_id)
            .where(
                CampaignRedemptionModel.campaign_id.in_(campaign_ids),
                CampaignRedemptionModel.released_at.is_(None),
                OrderModel.payment_status == "paid",
            )
            .group_by(CampaignRedemptionModel.campaign_id)
        )
        return {cid: (int(n), float(d), float(s)) for cid, n, d, s in (await self._session.execute(stmt)).all()}

    # ------------------------------------------------------------------
    # Público (cuántos clientes alcanza una campaña)
    # ------------------------------------------------------------------

    async def customer_count(self) -> int:
        from app.modules.iam.infra.models import UserModel

        stmt = select(func.count()).select_from(UserModel).where(UserModel.role == "user", UserModel.is_active.is_(True))
        return int((await self._session.execute(stmt)).scalar() or 0)

    async def owners_with_birthday_in_month(self, month: int) -> int:
        """Dueños con al menos una mascota (no borrada) que nació en ese mes."""
        from app.modules.pets.infra.models import PetModel

        stmt = select(func.count(func.distinct(PetModel.owner_id))).where(
            PetModel.deleted_at.is_(None), PetModel.birth_date.is_not(None), extract("month", PetModel.birth_date) == month,
        )
        return int((await self._session.execute(stmt)).scalar() or 0)
