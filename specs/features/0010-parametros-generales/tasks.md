---
feature: 0010-parametros-generales
plan: ./plan.md
---

# Tasks — Parámetros generales

## Backend
- [x] 1. Dominio con parámetros, validación y valores por defecto.
- [x] 2. Modelo, repositorio y migración `0d1e2f3a4b5c` (no ejecutada).
- [x] 3. `GET` / `PATCH /admin/settings`; registro en `app/main.py` y `alembic/env.py`.
- [x] 4. Anticipación mínima en `GET /availability` y `POST /holds` (`DATE_TOO_SOON`).
- [x] 5. Tests (`tests/unit/test_general_settings.py`).
- [x] 6. Entrada C-35 en `docs/cambios-api-para-front.md`.

## Frontend
- [ ] Admin: la página arma el formulario con `sections` y guarda con `PATCH` (solo lo cambiado).
- [ ] App de clientes: mostrar `detail.message` de `DATE_TOO_SOON`.

## Cierre
- [ ] Spec a `done`, índice actualizado, commit referencia la carpeta.
