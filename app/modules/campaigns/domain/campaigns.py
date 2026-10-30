"""Campañas y promociones (feature 0013): descuentos por segmento de cliente.

Decisiones del dueño (2026-10-29):
- Cada campaña es **automática** (se aplica sola si el cliente es de su público) o **con código** (el cliente
  escribe el cupón y se valida que sea de su público).
- Si aplican varias, se usa **solo la mejor** (la de mayor descuento). Una campaña por orden.
- Usos **configurables por campaña**: por cliente y, opcional, un tope total.
- Público "primera compra": clientes registrados sin ningún servicio (el segmento "nuevo" de Clientes exige uno).

El descuento se calcula sobre el subtotal de la orden (servicio + adicionales) y nunca lo supera.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from app.modules.crm.domain.customers import SEGMENTS

# Público de una campaña: los segmentos de Clientes + estos tres
AUDIENCES: dict[str, str] = {
    "todos": "Todos los clientes",
    "primera_compra": "Primera compra (sin servicios)",
    **{code: label for code, (label, _) in SEGMENTS.items()},
    "cumpleanos": "Mascota de cumpleaños este mes",
}
BENEFITS: dict[str, str] = {
    "percent": "Porcentaje de descuento",
    "amount": "Monto fijo de descuento",
    "free_addon": "Adicional gratis",
}
CHANNELS: dict[str, str] = {"push": "Push en la app", "whatsapp": "WhatsApp", "email": "Correo"}
# Estado que pone el admin; el que se muestra (activa, programada, finalizada…) sale de `display_state`
STATUSES: tuple[str, ...] = ("draft", "active", "paused", "ended")
DISPLAY_STATES: dict[str, str] = {
    "borrador": "Borrador",
    "programada": "Programada",
    "activa": "Activa",
    "pausada": "Pausada",
    "finalizada": "Finalizada",
}


class CampaignInvalid(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Campaign:
    id: UUID
    code: str                         # cupón (en mayúsculas); en las automáticas sirve de referencia
    name: str
    objective: Optional[str]
    audience: str
    benefit_type: str                 # percent | amount | free_addon
    value: float                      # % (percent) o S/ (amount); en free_addon no se usa
    addon_code: Optional[str]         # free_addon: código del adicional (ADD_…)
    channels: list[str]
    starts_on: date
    ends_on: Optional[date]           # None = sin fecha de fin
    status: str                       # draft | active | paused | ended
    automatic: bool
    max_uses_per_customer: Optional[int]   # None = sin límite
    max_total_uses: Optional[int]          # None = sin tope
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None


def display_state(c: Campaign, *, today: date, total_uses: int = 0) -> str:
    """Estado que ve el admin: borrador, pausada, programada, activa o finalizada."""
    if c.status == "draft":
        return "borrador"
    if c.status == "ended" or (c.ends_on is not None and c.ends_on < today):
        return "finalizada"
    if c.max_total_uses is not None and total_uses >= c.max_total_uses:
        return "finalizada"
    if c.status == "paused":
        return "pausada"
    return "programada" if c.starts_on > today else "activa"


def validate_fields(f: dict) -> None:
    """Valida una campaña completa (después de aplicar los cambios)."""
    if not (f.get("name") or "").strip():
        raise CampaignInvalid("CAMPAIGN_NAME_REQUIRED", "La campaña necesita un nombre.")
    code = f.get("code") or ""
    if not code or len(code) > 30 or not all(ch.isalnum() or ch in "-_" for ch in code):
        raise CampaignInvalid("CAMPAIGN_CODE_INVALID", "El código usa letras, números, - o _ (hasta 30).")
    if f.get("audience") not in AUDIENCES:
        raise CampaignInvalid("CAMPAIGN_AUDIENCE_INVALID", "Público inválido. Usa uno de: " + ", ".join(AUDIENCES) + ".")
    benefit = f.get("benefit_type")
    if benefit not in BENEFITS:
        raise CampaignInvalid("CAMPAIGN_BENEFIT_INVALID", "Beneficio inválido: percent, amount o free_addon.")
    value = f.get("value") or 0
    if benefit == "percent" and not 0 < value <= 100:
        raise CampaignInvalid("CAMPAIGN_VALUE_INVALID", "El porcentaje va de 1 a 100.")
    if benefit == "amount" and not value > 0:
        raise CampaignInvalid("CAMPAIGN_VALUE_INVALID", "El monto debe ser mayor que 0.")
    if benefit == "free_addon" and not (f.get("addon_code") or "").strip():
        raise CampaignInvalid("CAMPAIGN_ADDON_REQUIRED", "Indica el código del adicional que se regala (ADD_…).")
    if any(ch not in CHANNELS for ch in f.get("channels") or []):
        raise CampaignInvalid("CAMPAIGN_CHANNEL_INVALID", "Canal inválido: push, whatsapp o email.")
    if f.get("status") not in STATUSES:
        raise CampaignInvalid("CAMPAIGN_STATUS_INVALID", "Estado inválido: draft, active, paused o ended.")
    if f.get("ends_on") is not None and f["ends_on"] < f["starts_on"]:
        raise CampaignInvalid("CAMPAIGN_DATES_INVALID", "La fecha de fin no puede ser anterior a la de inicio.")
    for key in ("max_uses_per_customer", "max_total_uses"):
        if f.get(key) is not None and f[key] < 1:
            raise CampaignInvalid("CAMPAIGN_USES_INVALID", "Los límites de uso son de 1 en adelante (vacío = sin límite).")


def normalize_code(code: Optional[str]) -> str:
    return (code or "").strip().upper()


# ─── Aplicación a una compra ─────────────────────────────────────────────────

@dataclass(frozen=True)
class PurchaseLine:
    kind: str                      # service_base | service_addon
    amount: float                  # precio × cantidad
    addon_code: Optional[str] = None


@dataclass(frozen=True)
class Buyer:
    """Lo que decide el público: segmento de Clientes (None sin servicios) y mes de nacimiento de la mascota."""
    segment: Optional[str]
    services: int
    pet_birth_month: Optional[int]


def audience_matches(audience: str, buyer: Buyer, *, today: date) -> bool:
    if audience == "todos":
        return True
    if audience == "primera_compra":
        return buyer.services == 0
    if audience == "cumpleanos":
        return buyer.pet_birth_month == today.month
    return buyer.segment == audience


def subtotal(lines: list[PurchaseLine]) -> float:
    return round(sum(l.amount for l in lines), 2)


def discount_for(c: Campaign, lines: list[PurchaseLine]) -> float:
    """Descuento de la campaña sobre la compra (0 si no aplica). Nunca supera el subtotal."""
    total = subtotal(lines)
    if c.benefit_type == "percent":
        amount = total * c.value / 100
    elif c.benefit_type == "amount":
        amount = c.value
    else:  # free_addon: el adicional tiene que estar en la compra
        amount = sum(l.amount for l in lines if l.kind == "service_addon" and l.addon_code == c.addon_code)
    return round(min(amount, total), 2)


def purchase_lines(items_snapshot: Any, addon_codes: dict[str, Optional[str]]) -> list[PurchaseLine]:
    """Líneas de la compra desde los ítems del carrito u orden. `addon_codes`: id del adicional → código."""
    out = []
    for line in items_snapshot or []:
        if not isinstance(line, dict) or line.get("kind") not in ("service_base", "service_addon"):
            continue
        amount = float(line.get("unit_price") or 0) * int(line.get("qty") or 1)
        out.append(PurchaseLine(line["kind"], amount, addon_codes.get(str(line.get("ref_id")))))
    return out


@dataclass(frozen=True)
class Offer:
    campaign: Campaign
    discount: float


def best_offer(offers: list[Offer]) -> Optional[Offer]:
    """La de mayor descuento; empate → la que empezó antes (y luego por código)."""
    valid = [o for o in offers if o.discount > 0]
    if not valid:
        return None
    return sorted(valid, key=lambda o: (-o.discount, o.campaign.starts_on, o.campaign.code))[0]
