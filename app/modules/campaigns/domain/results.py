"""Resultados de una campaña (feature 0017): ventas, clientes, descuento, cobrado, costo estimado y margen.

- **Vendidas:** órdenes de servicio con la campaña, **pagadas y no canceladas** (lo mismo que «usos en órdenes
  pagadas» de la lista de campañas). **Realizadas:** de ellas, las terminadas.
- **Cliente nuevo:** antes de su primera compra con la campaña no tenía ningún servicio terminado (fuera de esa
  campaña).
- Montos: subtotal = suma de los ítems; descuento = el de la campaña; neto = total de la orden; cobrado = neto +
  cargos extra pagados.
- **Costo estimado** (insumos + mano de obra, el del dashboard) solo de las realizadas; si alguna no se puede costear
  queda fuera del margen y se informa cuántas tienen costo. Margen = cobrado de las costeadas − su costo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID


@dataclass(frozen=True)
class CampaignSale:
    order_id: UUID
    campaign_id: UUID
    user_id: UUID
    bought_at: datetime        # creación de la orden (checkout)
    done: bool
    subtotal: float
    discount: float
    net: float
    extra_paid: float
    cost: Optional[float]      # solo realizadas; None si no se pudo costear

    @property
    def collected(self) -> float:
        return self.net + self.extra_paid


@dataclass(frozen=True)
class CampaignResult:
    sold: int
    done: int
    customers: int
    new_customers: int
    subtotal: float
    discount: float
    discount_pct: Optional[float]   # descuento ÷ subtotal
    net: float
    extra_paid: float
    collected: float
    costed: int                     # realizadas con costo estimado
    cost: Optional[float]           # None si ninguna se pudo costear
    margin: Optional[float]
    margin_pct: Optional[float]     # margen ÷ cobrado de las costeadas


def summarize(sales: Iterable[CampaignSale], prior_service: dict[UUID, datetime]) -> CampaignResult:
    """`prior_service`: por cliente, su primer servicio terminado sin contar las órdenes de esta campaña."""
    sales = list(sales)
    first_buy: dict[UUID, datetime] = {}
    for s in sales:
        if s.user_id not in first_buy or s.bought_at < first_buy[s.user_id]:
            first_buy[s.user_id] = s.bought_at
    new = sum(1 for u, at in first_buy.items() if u not in prior_service or prior_service[u] >= at)

    subtotal = round(sum(s.subtotal for s in sales), 2)
    discount = round(sum(s.discount for s in sales), 2)
    costed = [s for s in sales if s.done and s.cost is not None]
    cost = round(sum(s.cost for s in costed), 2) if costed else None
    costed_collected = round(sum(s.collected for s in costed), 2)
    margin = round(costed_collected - cost, 2) if cost is not None else None
    return CampaignResult(
        sold=len(sales), done=sum(1 for s in sales if s.done), customers=len(first_buy), new_customers=new,
        subtotal=subtotal, discount=discount,
        discount_pct=round(discount / subtotal * 100, 1) if subtotal > 0 else None,
        net=round(sum(s.net for s in sales), 2), extra_paid=round(sum(s.extra_paid for s in sales), 2),
        collected=round(sum(s.collected for s in sales), 2), costed=len(costed), cost=cost, margin=margin,
        margin_pct=round(margin / costed_collected * 100, 1) if margin is not None and costed_collected > 0 else None,
    )
