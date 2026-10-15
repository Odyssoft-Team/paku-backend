---
feature: 0008-recomendaciones-v2
spec: ./spec.md
---

# Plan

- `store/domain/recommendations.py`: preguntas (fijas), `Rule`, `PetContext`, `recommend_service`,
  `evaluate_addons`, `validate_answers`, `questions_for`. Segmento = `breeds.coat_type` → S1–S6.
- Tabla `recommendation_rules` (migración `7a8b9c0d1e2f`, semilla con las hojas 17 y 19). Códigos en
  `store_products.code` y `store_addons.code` / `requires_photo` / `duration_extra_min` (por nombre).
- `store/app/use_cases_impl/recommend.py` + `POST /store/recommendations`.
- `recommendation_snapshot.py`: snapshot en el carrito (`CartPricing`) y lectura en la orden.
- Órdenes: `review_status/review_note/reviewed_at`; `POST /admin/orders/{id}/review`; bloqueo en `AssignOrder`;
  fotos `pre_service` del dueño (`AddPreServicePhoto`, media entity `order`); `PayOrder` exige fotos.
- `weight_balance.register_measured_weight`: sin cobro ni aviso.
- Tests: `test_recommendations.py` (reglas de la migración), `test_weight_balance.py`, `test_cart_pricing.py`.
