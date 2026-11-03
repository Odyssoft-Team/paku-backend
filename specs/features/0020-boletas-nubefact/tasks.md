---
feature: 0020-boletas-nubefact
plan: ./plan.md
---

# Tasks — Boletas con Nubefact

## Fase 1 — conexión y capacidades
- [x] 1. Módulo `invoicing`: tabla `invoicing_providers` (migración `6d7e8f9a0b1c`), token cifrado.
- [x] 2. `NubefactClient` y prueba de conexión con `consultar_comprobante` (no emite).
- [x] 3. `GET/PUT /admin/integrations/nubefact`, `POST /admin/integrations/nubefact/test` con `readiness`.
- [x] 4. Tests (`tests/unit/test_invoicing_nubefact.py`). C-47.
- [x] 5. Admin: tarjeta en Integraciones y vista «Qué se puede hacer».
- [ ] Cierre fase 1: migración en el servidor y prueba con la cuenta (o DEMO) de Nubefact.

## Fase 2 — emisión (pendiente de las decisiones del spec)
