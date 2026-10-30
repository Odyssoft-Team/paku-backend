---
feature: 0011-clientes-crm
plan: ./plan.md
---

# Tasks — Clientes (CRM)

## Backend
- [x] 1. Dominio: visitas, métricas y segmentos.
- [x] 2. Repositorio de lectura (sin migración).
- [x] 3. Casos de uso y rutas `/admin/customers*`; registro en `app/main.py`.
- [x] 4. Tests (`tests/unit/test_crm_customers.py`).
- [x] 5. Entrada C-36 en `docs/cambios-api-para-front.md`.

## Frontend
- [ ] Admin: Clientes y su ficha con `lib/services/customers.ts` (deja de usar `lib/mock/crm.ts` en esa vista).

## Cierre
- [ ] Spec a `done`, índice actualizado, commit referencia la carpeta.
