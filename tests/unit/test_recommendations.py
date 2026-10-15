"""Feature 0008 — motor de recomendaciones (hojas 17–20 del documento V2), con las reglas de la migración."""
import importlib.util
from pathlib import Path

import pytest

from app.modules.store.domain.recommendations import (
    OFFER,
    RECOMMEND,
    UNAVAILABLE,
    PetContext,
    Rule,
    evaluate_addons,
    questions_for,
    recommend_service,
    validate_answers,
)

_MIG = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "7a8b9c0d1e2f_recommendations_v2.py"
_spec = importlib.util.spec_from_file_location("mig_rec_v2", _MIG)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
RULES = [Rule(id=r[0], kind=r[1], priority=r[2], active=True, action=r[3], conditions=r[4], target_code=r[5],
              requires_photo=r[6], text=r[7]) for r in _mod._RULES]
ALL_SERVICES = {"Clásico", "Medicado", "Premium", "Seco"}
ALL_ADDONS = {"ADD_DESLANADO_INT", "ADD_DESMOTADO_LOC", "ADD_DESMOTADO_EXT", "ADD_CORTE_EST", "ADD_RETOQUE",
              "ADD_TOOTHBRUSH"}


def pet(age=24, weight=12.0, seg="S2", skin=False):
    return PetContext(age_months=age, weight_kg=weight, segment=seg, skin_sensitive=skin)


@pytest.mark.parametrize(
    "ctx, rule_id, code",
    [
        (pet(age=3, weight=8, seg="S2"), "REC-001", "Seco"),            # cachorro: prevalece
        (pet(seg="S3", skin=True), "REC-002", "Medicado"),              # piel sensible gana a REC-005
        (pet(seg="S3"), "REC-005", "Premium"),                          # rizado/lanoso → Spa Deluxe
        (pet(seg="S5"), "REC-003", "Premium"),
        (pet(seg="S6"), "REC-004", "Premium"),
        (pet(seg="S1"), "REC-006", "Clásico"),
        (pet(seg="S4"), "REC-008", "Clásico"),
        (pet(seg=None), "REC-999", "Clásico"),                          # sin clasificación: respaldo
        (pet(age=None, seg="S5"), "REC-003", "Premium"),                # sin fecha de nacimiento: adulto
    ],
)
def test_service_recommendation(ctx, rule_id, code):
    rule = recommend_service(RULES, ctx, ALL_SERVICES)
    assert (rule.id, rule.target_code) == (rule_id, code)


def test_recommendation_skips_services_the_pet_cannot_buy():
    # Cachorro, pero Express sin agua no está disponible → la siguiente regla que aplique
    rule = recommend_service(RULES, pet(age=3, weight=8, seg="S3"), {"Clásico", "Premium"})
    assert rule.id == "REC-999"  # REC-005 exige ≥5 meses


def test_inactive_rule_is_ignored():
    rules = [r if r.id != "REC-005" else Rule(**{**r.__dict__, "active": False}) for r in RULES]
    assert recommend_service(rules, pet(seg="S3"), ALL_SERVICES).id == "REC-999"


def _addons(ctx, service, answers):
    return evaluate_addons(RULES, ctx, service_code=service, answers=answers, addon_codes=ALL_ADDONS)


def test_addon_rules():
    ev = _addons(pet(seg="S4"), "Clásico", {"Q-SHEDDING": "HIGH", "Q-TOOTHBRUSH": "NO"})
    assert ev.verdicts["ADD_DESLANADO_INT"].action == RECOMMEND
    assert ev.verdicts["ADD_TOOTHBRUSH"].action == OFFER
    assert ev.review is None

    ev = _addons(pet(seg="S2"), "Clásico", {"Q-MATTING": "EXTENDED"})
    v = ev.verdicts["ADD_DESMOTADO_EXT"]
    assert v.action == RECOMMEND and v.requires_photo

    ev = _addons(pet(seg="S2"), "Premium", {"Q-MATTING": "SEVERE"})
    assert ev.review is not None and ev.review.id == "AR-022" and ev.review.requires_photo

    assert _addons(pet(seg="S6", weight=10), "Clásico", {"Q-STYLING": "RETOUCH"}).verdicts["ADD_RETOQUE"].action == RECOMMEND
    assert _addons(pet(seg="S6", weight=30), "Clásico", {"Q-STYLING": "RETOUCH"}).verdicts["ADD_RETOQUE"].action == UNAVAILABLE

    # Sin respuesta que la dispare, el adicional queda disponible sin recomendación
    assert _addons(pet(seg="S4"), "Clásico", {"Q-SHEDDING": "NORMAL"}).verdicts["ADD_DESLANADO_INT"].action is None


def test_express_only_keeps_toothbrush():
    ev = _addons(pet(age=3, weight=8, seg="S2"), "Seco", {})
    assert ev.verdicts["ADD_TOOTHBRUSH"].action is None
    assert all(ev.verdicts[c].action == UNAVAILABLE for c in ALL_ADDONS - {"ADD_TOOTHBRUSH"})


def test_questions_by_segment_and_validation():
    assert [q.id for q in questions_for("S4")] == ["Q-SHEDDING", "Q-TOOTHBRUSH"]
    assert [q.id for q in questions_for("S2")] == ["Q-MATTING", "Q-STYLING", "Q-TOOTHBRUSH"]
    assert [q.id for q in questions_for(None)] == ["Q-TOOTHBRUSH"]
    assert validate_answers({"Q-MATTING": "SEVERE"}) == {"Q-MATTING": "SEVERE"}
    with pytest.raises(ValueError):
        validate_answers({"Q-MATTING": "muchos nudos"})  # BR-028: nada de texto libre
    with pytest.raises(ValueError):
        validate_answers({"Q-OTRA": "YES"})


# ─── Lo que se guarda en la reserva y el bloqueo del pago sin fotos ─────────────

import asyncio  # noqa: E402
from datetime import date  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from uuid import uuid4  # noqa: E402

from fastapi import HTTPException  # noqa: E402

from app.modules.store.app.use_cases_impl.recommendation_snapshot import build_recommendation_snapshot  # noqa: E402
from app.modules.store.domain.models import Addon, Product, Species  # noqa: E402

CAT = uuid4()


class _Store:
    def __init__(self):
        self.products = {
            pid: Product(id=pid, category_id=CAT, name=name, species=Species.dog, allowed_breeds=None,
                         is_active=True, code=code)
            for pid, name, code in [(uuid4(), "Fresco y Limpio", "Clásico"), (uuid4(), "Spa Deluxe", "Premium")]
        }
        self.clasico = next(p for p in self.products.values() if p.code == "Clásico")
        self.addons = [
            Addon(id=uuid4(), product_id=self.clasico.id, name="Corte estético", species=Species.dog,
                  allowed_breeds=None, is_active=True, code="ADD_CORTE_EST", requires_photo=True),
            Addon(id=uuid4(), product_id=self.clasico.id, name="Desmotado localizado", species=Species.dog,
                  allowed_breeds=None, is_active=True, code="ADD_DESMOTADO_LOC"),
        ]

    async def list_recommendation_rules(self):
        return RULES

    async def breed_coat_type(self, breed_id):
        return "curly_no_undercoat"  # S3

    async def get_product(self, pid):
        return self.products.get(pid)

    async def list_products(self, *, category_id, species=None):
        return list(self.products.values())

    async def list_addons(self, *, product_id):
        return [a for a in self.addons if a.product_id == product_id]

    async def price_for(self, **kw):
        return 90.0


def _snapshot(store, answers, selected):
    pet_ = SimpleNamespace(breed_id="poodle", weight_kg=8.0, birth_date=date(2023, 1, 1), skin_sensitivity=False)
    return asyncio.run(build_recommendation_snapshot(
        store, pet=pet_, product_id=store.clasico.id, addon_ids=[a.id for a in selected], answers=answers,
        breed_category="curly_no_undercoat"))


def test_snapshot_records_rules_photos_and_review():
    store = _Store()
    snap = _snapshot(store, {"Q-STYLING": "FULL_CUT"}, [store.addons[0]])
    assert snap["version"] == "PAKU-REC-V1"
    assert snap["recommended_service_code"] == "Premium" and snap["service_rule_id"] == "REC-005"
    assert snap["chose_recommended"] is False
    assert snap["requires_photos"] is True and snap["photo_addons"] == ["ADD_CORTE_EST"]
    assert {"code": "ADD_CORTE_EST", "action": "RECOMENDAR", "rule_id": "AR-030", "selected": True} in snap["addons"]
    assert snap["review_required"] is False

    snap = _snapshot(store, {"Q-MATTING": "SEVERE"}, [])
    assert snap["review_required"] is True and snap["review_rule_id"] == "AR-022" and snap["requires_photos"] is True


def test_pay_requires_photos():
    from app.modules.orders.app.use_cases_impl.payment import _assert_required_photos

    class _Photos:
        def __init__(self, has):
            self.has = has

        async def has_kind(self, order_id, kind):
            return self.has

    order = SimpleNamespace(id=uuid4(), items_snapshot=[{"kind": "service_base", "meta": {"recommendation": {
        "requires_photos": True, "photo_addons": ["ADD_CORTE_EST"]}}}])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_assert_required_photos(order, _Photos(False)))
    assert exc.value.status_code == 409 and exc.value.detail["code"] == "PHOTOS_REQUIRED"
    asyncio.run(_assert_required_photos(order, _Photos(True)))  # con foto: pasa
    order.items_snapshot[0]["meta"]["recommendation"]["requires_photos"] = False
    asyncio.run(_assert_required_photos(order, _Photos(False)))  # sin requisito: pasa
