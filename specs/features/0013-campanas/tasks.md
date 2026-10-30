---
feature: 0013-campanas
plan: ./plan.md
---

# Tasks — Campañas

## Backend
- [x] 1. Módulo `campaigns` + migración `2f3a4b5c6d7e`.
- [x] 2. Descuento en `POST /orders` (`campaign_code`), uso de la campaña y liberación al cancelar.
- [x] 3. `POST /campaigns/quote`.
- [x] 4. Tests (`tests/unit/test_campaigns.py`).
- [x] 5. Entrada C-38 en `docs/cambios-api-para-front.md`.

## Frontend
- [ ] Admin: CRM · Campañas con la API.
- [ ] App de clientes: cupón, vista previa y total con descuento.

## Cierre
- [ ] Respuesta a las preguntas abiertas (total S/ 0).
- [ ] Spec a `done`, índice actualizado, commit referencia la carpeta.
