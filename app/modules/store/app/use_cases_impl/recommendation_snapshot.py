"""Recomendación que se guarda en la reserva (feature 0008, BR-030): respuestas del cliente, regla que
recomendó el servicio, reglas de adicionales, y si la reserva requiere fotos o revisión manual."""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from app.modules.store.app.use_cases_impl.recommend import addon_snapshot, pet_context
from app.modules.store.domain.eligibility import ineligibility
from app.modules.store.domain.recommendations import (
    RECOMMENDATION_VERSION,
    evaluate_addons,
    recommend_service,
)


async def build_recommendation_snapshot(
    store_repo, *, pet, product_id: UUID, addon_ids: list[UUID], answers: dict[str, str], breed_category: str,
) -> dict[str, Any]:
    rules = await store_repo.list_recommendation_rules()
    ctx = await pet_context(store_repo, pet)
    product = await store_repo.get_product(product_id)
    weight = ctx.weight_kg

    # Servicios de la categoría que la mascota podía comprar (para auditar qué se le recomendó)
    available: set[str] = set()
    for p in await store_repo.list_products(category_id=product.category_id):
        if not p.code or not p.is_active:
            continue
        if ineligibility(p, weight=weight, birth_date=getattr(pet, "birth_date", None)) is not None:
            continue
        if await store_repo.price_for(target_id=p.id, target_type="product", species=p.species,
                                      breed_category=breed_category, weight=weight) is not None:
            available.add(p.code)
    service_rule = recommend_service(rules, ctx, available)

    addons = await store_repo.list_addons(product_id=product_id)
    codes = {a.code for a in addons if a.code}
    selected = [a for a in addons if a.id in set(addon_ids)]
    ev = evaluate_addons(rules, ctx, service_code=product.code, answers=answers, addon_codes=codes)

    review_rule = ev.review
    requires_photos = any(a.requires_photo for a in selected) or bool(review_rule and review_rule.requires_photo)
    return {
        "version": RECOMMENDATION_VERSION,
        "answers": answers,
        "recommended_service_code": service_rule.target_code if service_rule else None,
        "service_rule_id": service_rule.id if service_rule else None,
        "chose_recommended": bool(service_rule and service_rule.target_code == product.code),
        **addon_snapshot(ev, {a.code for a in selected if a.code}),
        "requires_photos": requires_photos,
        "photo_addons": [a.code or a.name for a in selected if a.requires_photo],
        "review_required": review_rule is not None,
        "review_text": review_rule.text if review_rule else None,
    }


def recommendation_of(items_snapshot: Any) -> Optional[dict[str, Any]]:
    """La recomendación guardada en la línea del servicio base de una orden (o None)."""
    for line in items_snapshot or []:
        kind = line.get("kind") if isinstance(line, dict) else None
        if getattr(kind, "value", kind) == "service_base":
            meta = line.get("meta") or {}
            return meta.get("recommendation") if isinstance(meta, dict) else None
    return None
