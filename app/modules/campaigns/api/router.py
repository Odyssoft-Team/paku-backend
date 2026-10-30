"""Campañas y promociones (feature 0013): administración (admin) y vista previa del descuento (cliente)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_roles
from app.core.db import engine, get_async_session
from app.modules.campaigns.api.schemas import (
    CampaignConfigOut,
    CampaignIn,
    CampaignOut,
    CampaignQuoteIn,
    CampaignQuoteOut,
    CampaignUpdateIn,
    CodeLabelOut,
)
from app.modules.campaigns.app.use_cases import CampaignRow, ListCampaigns, SaveCampaign, campaign_engine
from app.modules.campaigns.domain.campaigns import AUDIENCES, BENEFITS, CHANNELS, DISPLAY_STATES, Campaign
from app.modules.campaigns.infra.postgres_campaign_repository import PostgresCampaignRepository
from app.modules.crm.infra.postgres_customer_read_repository import PostgresCustomerReadRepository

router = APIRouter(prefix="/campaigns", tags=["campaigns"])
admin_router = APIRouter(prefix="/campaigns", tags=["campaigns-admin"])


def get_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresCampaignRepository:
    return PostgresCampaignRepository(session=session)


def get_crm_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresCustomerReadRepository:
    return PostgresCustomerReadRepository(session=session)


def benefit_label(c: Campaign) -> str:
    if c.benefit_type == "percent":
        return f"{c.value:g} % de descuento"
    if c.benefit_type == "amount":
        return f"S/ {c.value:.2f} de descuento"
    return f"Adicional {c.addon_code} gratis"


def _out(row: CampaignRow) -> CampaignOut:
    c = row.campaign
    return CampaignOut(
        id=c.id, code=c.code, name=c.name, objective=c.objective, audience=c.audience,
        audience_label=AUDIENCES.get(c.audience, c.audience), benefit_type=c.benefit_type,
        benefit_label=benefit_label(c), value=c.value, addon_code=c.addon_code, channels=c.channels,
        starts_on=c.starts_on, ends_on=c.ends_on, status=c.status, state=row.state, automatic=c.automatic,
        max_uses_per_customer=c.max_uses_per_customer, max_total_uses=c.max_total_uses, uses=row.uses,
        paid_uses=row.paid_uses, discount_given=row.discount_given, sales=row.sales,
        audience_size=row.audience_size, created_at=c.created_at, updated_at=c.updated_at,
    )


# ------------------------------------------------------------------
# Admin
# ------------------------------------------------------------------

@admin_router.get("/config", response_model=CampaignConfigOut)
async def campaigns_config(_: CurrentUser = Depends(require_roles("admin"))) -> CampaignConfigOut:
    """Públicos (segmentos de Clientes + todos, primera compra, cumpleaños), beneficios, canales y estados."""
    as_list = lambda d: [CodeLabelOut(code=k, label=v) for k, v in d.items()]  # noqa: E731
    return CampaignConfigOut(audiences=as_list(AUDIENCES), benefits=as_list(BENEFITS), channels=as_list(CHANNELS),
                             states=as_list(DISPLAY_STATES))


@admin_router.get("", response_model=list[CampaignOut])
async def list_campaigns(
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCampaignRepository = Depends(get_repo),
    crm_repo: PostgresCustomerReadRepository = Depends(get_crm_repo),
) -> list[CampaignOut]:
    """Campañas con su estado, usos, resultados (órdenes pagadas) y tamaño del público hoy."""
    return [_out(r) for r in await ListCampaigns(repo=repo, crm_repo=crm_repo).execute()]


async def _row(campaign: Campaign, repo, crm_repo) -> CampaignOut:
    rows = await ListCampaigns(repo=repo, crm_repo=crm_repo).execute()
    return _out(next(r for r in rows if r.campaign.id == campaign.id))


@admin_router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignIn,
    current: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCampaignRepository = Depends(get_repo),
    crm_repo: PostgresCustomerReadRepository = Depends(get_crm_repo),
) -> CampaignOut:
    """Crea una campaña. 409 `CAMPAIGN_CODE_TAKEN` si el código ya existe."""
    campaign = await SaveCampaign(repo=repo).execute(payload.model_dump(), actor_id=current.id)
    return await _row(campaign, repo, crm_repo)


@admin_router.patch("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: UUID,
    payload: CampaignUpdateIn,
    current: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresCampaignRepository = Depends(get_repo),
    crm_repo: PostgresCustomerReadRepository = Depends(get_crm_repo),
) -> CampaignOut:
    """Edita, activa (`status=active`), pausa o termina una campaña. Los usos ya registrados no cambian."""
    fields = {k: getattr(payload, k) for k in payload.model_fields_set}
    campaign = await SaveCampaign(repo=repo).execute(fields, campaign_id=campaign_id, actor_id=current.id)
    return await _row(campaign, repo, crm_repo)


# ------------------------------------------------------------------
# Cliente
# ------------------------------------------------------------------

@router.post("/quote", response_model=CampaignQuoteOut)
async def quote_campaign(
    payload: CampaignQuoteIn,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CampaignQuoteOut:
    """
    Descuento que tendría el carrito: la mejor entre las campañas automáticas del cliente y el cupón (si lo
    envía). Cupón inválido → 422 con `code` (CAMPAIGN_CODE_NOT_FOUND, CAMPAIGN_NOT_ACTIVE, CAMPAIGN_ALREADY_USED,
    CAMPAIGN_NOT_FOR_CUSTOMER, CAMPAIGN_NOT_APPLICABLE). Se aplica de verdad al crear la orden
    (`POST /orders` con el mismo `campaign_code`).
    """
    from app.modules.cart.app.use_cases import GetCart
    from app.modules.cart.infra.postgres_cart_repository import PostgresCartRepository
    from app.modules.orders.app.use_cases import _snapshot_cart_items

    cart_repo = PostgresCartRepository(session=session, engine=engine)
    await GetCart(repo=cart_repo).execute(cart_id=payload.cart_id, user_id=current.id)  # 404 / 410 si no es suyo o venció
    items = _snapshot_cart_items(await cart_repo.list_items(cart_id=payload.cart_id, user_id=current.id))
    quote = await campaign_engine(session).quote(user_id=current.id, items_snapshot=items, code=payload.code)
    c = quote.offer.campaign if quote.offer else None
    return CampaignQuoteOut(
        subtotal=quote.subtotal, discount=quote.discount, total=quote.total,
        campaign_id=c.id if c else None, campaign_name=c.name if c else None,
        benefit_label=benefit_label(c) if c else None, automatic=c.automatic if c else None,
    )
