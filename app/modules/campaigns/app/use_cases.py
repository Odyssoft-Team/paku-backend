"""Campañas (feature 0013): administración, mejor oferta para una compra y usos por orden."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.timezone import today_lima
from app.modules.campaigns.domain.campaigns import (
    AUDIENCES,
    Buyer,
    Campaign,
    CampaignInvalid,
    Offer,
    best_offer,
    audience_matches,
    discount_for,
    display_state,
    normalize_code,
    purchase_lines,
    subtotal,
    validate_fields,
)

logger = logging.getLogger(__name__)

_FIELDS = (
    "code", "name", "objective", "audience", "benefit_type", "value", "addon_code", "channels", "starts_on",
    "ends_on", "status", "automatic", "max_uses_per_customer", "max_total_uses",
)


def _error(status_code: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, **extra})


# ─── Administración ──────────────────────────────────────────────────────────

@dataclass
class SaveCampaign:
    repo: Any

    async def execute(self, fields: dict, *, campaign_id: Optional[UUID] = None, actor_id: UUID) -> Campaign:
        """Crea o edita (solo las claves enviadas). El código se guarda en mayúsculas y es único."""
        current: dict = {}
        if campaign_id is not None:
            existing = await self.repo.get(campaign_id)
            if existing is None:
                raise _error(status.HTTP_404_NOT_FOUND, "CAMPAIGN_NOT_FOUND", "Campaña no encontrada.")
            current = {k: getattr(existing, k) for k in _FIELDS}
        merged = {**{"status": "draft", "channels": [], "automatic": False, "value": 0}, **current,
                  **{k: v for k, v in fields.items() if k in _FIELDS}}
        merged["code"] = normalize_code(merged.get("code"))
        merged["name"] = (merged.get("name") or "").strip()
        merged["addon_code"] = (merged.get("addon_code") or "").strip() or None
        if merged.get("benefit_type") != "free_addon":
            merged["addon_code"] = None
        try:
            validate_fields(merged)
        except CampaignInvalid as exc:
            raise _error(422, exc.code, exc.message) from exc
        try:
            return await self.repo.save(merged, campaign_id=campaign_id, actor_id=actor_id)
        except ValueError as exc:
            if str(exc) == "code_taken":
                raise _error(status.HTTP_409_CONFLICT, "CAMPAIGN_CODE_TAKEN", "Ya hay una campaña con ese código.") from exc
            raise


@dataclass(frozen=True)
class CampaignRow:
    campaign: Campaign
    state: str
    uses: int                    # usos vigentes (para los topes)
    paid_uses: int
    discount_given: float
    sales: float
    audience_size: Optional[int]


@dataclass
class ListCampaigns:
    repo: Any
    crm_repo: Any

    async def execute(self, *, today: Optional[date] = None) -> list[CampaignRow]:
        from app.modules.crm.app.use_cases import BuildCustomers

        today = today or today_lima()
        campaigns = await self.repo.list_campaigns()
        ids = [c.id for c in campaigns]
        uses = await self.repo.uses(ids)
        results = await self.repo.results(ids)

        # Tamaño de cada público (hoy)
        customers = await BuildCustomers(repo=self.crm_repo).execute(today=today)
        sizes: dict[str, int] = {code: 0 for code in AUDIENCES}
        for c in customers:
            if c.metrics.segment:
                sizes[c.metrics.segment] += 1
        total = await self.repo.customer_count()
        sizes["todos"] = total
        sizes["primera_compra"] = max(total - len(customers), 0)
        sizes["cumpleanos"] = await self.repo.owners_with_birthday_in_month(today.month)

        out = []
        for c in campaigns:
            n, given, sales = results.get(c.id, (0, 0.0, 0.0))
            out.append(CampaignRow(
                campaign=c, state=display_state(c, today=today, total_uses=uses.get(c.id, 0)),
                uses=uses.get(c.id, 0), paid_uses=n, discount_given=round(given, 2), sales=round(sales, 2),
                audience_size=sizes.get(c.audience),
            ))
        return out


# ─── Mejor oferta para una compra ────────────────────────────────────────────

@dataclass(frozen=True)
class Quote:
    subtotal: float
    offer: Optional[Offer]

    @property
    def discount(self) -> float:
        return self.offer.discount if self.offer else 0.0

    @property
    def total(self) -> float:
        return round(self.subtotal - self.discount, 2)


@dataclass
class CampaignEngine:
    """Elige la campaña con mayor descuento entre las automáticas del público del cliente y la del código."""
    repo: Any
    crm_repo: Any
    pets_repo: Any
    store_repo: Any

    async def _buyer(self, user_id: UUID, items_snapshot: Any, today: date) -> Buyer:
        from app.modules.crm.app.use_cases import BuildCustomers

        found = await BuildCustomers(repo=self.crm_repo).execute(user_id=user_id, today=today)
        metrics = found[0].metrics if found else None
        month = None
        for line in items_snapshot or []:
            if isinstance(line, dict) and line.get("kind") == "service_base":
                meta = line.get("meta") if isinstance(line.get("meta"), dict) else {}
                try:
                    pet = await self.pets_repo.get_by_id(UUID(str(meta.get("pet_id"))))
                except ValueError:
                    pet = None
                if pet is not None and pet.birth_date is not None:
                    month = pet.birth_date.month
                break
        return Buyer(segment=metrics.segment if metrics else None, services=metrics.services if metrics else 0,
                     pet_birth_month=month)

    async def _lines(self, items_snapshot: Any):
        codes: dict[str, Optional[str]] = {}
        for line in items_snapshot or []:
            if isinstance(line, dict) and line.get("kind") == "service_addon":
                try:
                    addon = await self.store_repo.get_addon(UUID(str(line.get("ref_id"))))
                except ValueError:
                    addon = None
                codes[str(line.get("ref_id"))] = addon.code if addon else None
        return purchase_lines(items_snapshot, codes)

    async def _usable(self, c: Campaign, user_id: UUID, today: date) -> Optional[str]:
        """None si el cliente puede usarla; si no, el código de error."""
        total = (await self.repo.uses([c.id])).get(c.id, 0)
        if display_state(c, today=today, total_uses=total) != "activa":
            return "CAMPAIGN_NOT_ACTIVE"
        if c.max_uses_per_customer is not None:
            mine = (await self.repo.uses([c.id], user_id=user_id)).get(c.id, 0)
            if mine >= c.max_uses_per_customer:
                return "CAMPAIGN_ALREADY_USED"
        return None

    async def quote(self, *, user_id: UUID, items_snapshot: Any, code: Optional[str] = None,
                    today: Optional[date] = None) -> Quote:
        """Mejor oferta. Con `code` inválido responde 422 con el motivo (el cliente decide si sigue sin él)."""
        today = today or today_lima()
        lines = await self._lines(items_snapshot)
        buyer = await self._buyer(user_id, items_snapshot, today)
        offers: list[Offer] = []

        for c in await self.repo.list_campaigns():
            if not c.automatic or not audience_matches(c.audience, buyer, today=today):
                continue
            if await self._usable(c, user_id, today) is None:
                offers.append(Offer(c, discount_for(c, lines)))

        code = normalize_code(code)
        if code:
            c = await self.repo.get_by_code(code)
            messages = {
                "CAMPAIGN_NOT_ACTIVE": "Este cupón no está vigente.",
                "CAMPAIGN_ALREADY_USED": "Ya usaste este cupón.",
            }
            if c is None or c.status == "draft":
                raise _error(422, "CAMPAIGN_CODE_NOT_FOUND", "El cupón no existe.", coupon=code)
            problem = await self._usable(c, user_id, today)
            if problem:
                raise _error(422, problem, messages[problem], coupon=code)
            if not audience_matches(c.audience, buyer, today=today):
                raise _error(422, "CAMPAIGN_NOT_FOR_CUSTOMER", "Este cupón no aplica a tu cuenta.", coupon=code)
            discount = discount_for(c, lines)
            if discount <= 0:
                raise _error(422, "CAMPAIGN_NOT_APPLICABLE", "El cupón no aplica a esta compra.", coupon=code)
            offers.append(Offer(c, discount))

        return Quote(subtotal=subtotal(lines), offer=best_offer(offers))


def campaign_engine(session) -> CampaignEngine:
    """Motor con los repositorios de la sesión (lo usan las rutas de órdenes y campañas)."""
    from app.core.db import engine
    from app.modules.campaigns.infra.postgres_campaign_repository import PostgresCampaignRepository
    from app.modules.crm.infra.postgres_customer_read_repository import PostgresCustomerReadRepository
    from app.modules.pets.infra.postgres_pet_repository import PostgresPetRepository
    from app.modules.store.infra.postgres_store_repository import PostgresStoreRepository

    return CampaignEngine(
        repo=PostgresCampaignRepository(session=session),
        crm_repo=PostgresCustomerReadRepository(session=session),
        pets_repo=PostgresPetRepository(session=session, engine=engine),
        store_repo=PostgresStoreRepository(session=session, engine=engine),
    )


async def release_order_campaign(session, order) -> None:
    """Al cancelar una orden se libera el uso de su campaña (best effort)."""
    if getattr(order, "campaign_id", None) is None:
        return
    from app.modules.campaigns.infra.postgres_campaign_repository import PostgresCampaignRepository

    try:
        await PostgresCampaignRepository(session=session).release_for_order(order.id)
    except Exception as exc:
        logger.exception("No se pudo liberar el uso de campaña de la orden %s: %s", order.id, exc)
        try:
            await session.rollback()
        except Exception:
            pass
