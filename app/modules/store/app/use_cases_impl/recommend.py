"""POST /store/recommendations (feature 0008): qué servicio recomendar, qué preguntar y cómo mostrar cada
adicional para una mascota. Usa el motor de `store/domain/recommendations.py` con las reglas de la BD."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException

from app.modules.store.app.use_cases_impl.catalog import GetProduct, ListProducts
from app.modules.store.domain.eligibility import age_in_months
from app.modules.store.domain.recommendations import (
    RECOMMENDATION_VERSION,
    REVIEW,
    UNAVAILABLE,
    AddonEvaluation,
    PetContext,
    Question,
    evaluate_addons,
    questions_for,
    recommend_service,
    validate_answers,
)


@dataclass
class RecommendationResult:
    version: str
    segment: Optional[str]
    service: Optional[dict[str, Any]]
    questions: list[Question]
    addons: list[dict[str, Any]] = field(default_factory=list)
    review: Optional[dict[str, Any]] = None


async def pet_context(repo, pet) -> PetContext:
    from app.modules.store.domain.recommendations import SEGMENT_BY_COAT

    coat = await repo.breed_coat_type(getattr(pet, "breed_id", None))
    weight = getattr(pet, "weight_kg", None)
    return PetContext(
        age_months=age_in_months(getattr(pet, "birth_date", None)),
        weight_kg=float(weight) if weight is not None else None,
        segment=SEGMENT_BY_COAT.get(coat or ""),
        skin_sensitive=bool(getattr(pet, "skin_sensitivity", None)),
    )


def addon_snapshot(evaluation: AddonEvaluation, selected_codes: set[str]) -> dict[str, Any]:
    """Lo que se guarda en la orden (BR-030): reglas que aplicaron y si requiere revisión."""
    return {
        "addons": [
            {"code": v.code, "action": v.action, "rule_id": v.rule_id, "selected": v.code in selected_codes}
            for v in evaluation.verdicts.values() if v.action
        ],
        "review_rule_id": evaluation.review.id if evaluation.review else None,
    }


@dataclass
class Recommend:
    repo: Any
    pets_repo: Any

    async def execute(self, *, pet_id: UUID, product_id: Optional[UUID] = None,
                      answers: Optional[dict[str, Any]] = None) -> RecommendationResult:
        try:
            clean = validate_answers(answers)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "ANSWER_INVALID", "message": str(exc)}) from exc

        pet = await self.pets_repo.get_by_id(pet_id)
        if pet is None:
            raise HTTPException(status_code=404, detail="Pet not found")
        ctx = await pet_context(self.repo, pet)
        rules = await self.repo.list_recommendation_rules()

        # Servicio recomendado entre los que la mascota puede comprar en la categoría
        product = await self.repo.get_product(product_id) if product_id else None
        category = await self._category(product)
        eligible = await ListProducts(repo=self.repo, pets_repo=self.pets_repo).execute(
            category_slug=category.slug, pet_id=pet_id) if category else []
        by_code = {rp.product.code: rp.product for rp in eligible if rp.product.code and rp.price is not None}
        rule = recommend_service(rules, ctx, set(by_code))
        service = None
        if rule is not None:
            p = by_code[rule.target_code]
            service = {"product_id": p.id, "code": p.code, "name": p.name, "rule_id": rule.id, "text": rule.text}

        questions = questions_for(ctx.segment)
        result = RecommendationResult(version=RECOMMENDATION_VERSION, segment=ctx.segment, service=service,
                                      questions=questions)
        if product is None:
            return result

        # Adicionales del servicio elegido
        _, resolved = await GetProduct(repo=self.repo, pets_repo=self.pets_repo).execute(
            product_id=product.id, pet_id=pet_id)
        codes = {ra.addon.code for ra in resolved if ra.addon.code}
        ev = evaluate_addons(rules, ctx, service_code=product.code, answers=clean, addon_codes=codes)
        for ra in resolved:
            v = ev.verdicts.get(ra.addon.code or "")
            if v is not None and v.action == UNAVAILABLE:
                continue
            result.addons.append({
                "addon_id": ra.addon.id, "code": ra.addon.code, "name": ra.addon.name, "price": ra.price,
                "action": v.action if v else None, "rule_id": v.rule_id if v else None,
                "text": v.text if v else None,
                "requires_photo": bool(ra.addon.requires_photo or (v and v.requires_photo)),
            })
        if ev.review is not None:
            result.review = {"rule_id": ev.review.id, "text": ev.review.text, "requires_photo": ev.review.requires_photo}

        # Solo las preguntas que disparan algo en este servicio
        relevant = {r.conditions.get("question") for r in rules
                    if r.kind == "addon" and r.active and (r.target_code in codes or r.action == REVIEW)
                    and (not r.conditions.get("services") or product.code in r.conditions["services"])}
        result.questions = [q for q in questions if q.id in relevant]
        return result

    async def _category(self, product):
        if product is not None:
            return await self.repo.get_category(product.category_id)
        for c in await self.repo.list_categories():
            if c.is_active:
                return c
        return None
