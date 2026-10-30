---
feature: 0009-inventario
plan: ./plan.md
---

# Tasks — Inventario

## Backend
- [x] 1. Dominio (`domain/inventory.py`) con reglas puras.
- [x] 2. Modelos, repositorio y migración `9c0d1e2f3a4b` (no ejecutada).
- [x] 3. Casos de uso: insumos, movimientos, recetas (tabla pelaje × peso), resumen, costo y consumo por orden.
- [x] 4. Rutas `/admin/inventory/*` y registro en `app/main.py` y `alembic/env.py`.
- [x] 5. Consumo automático al pasar a `done` (groomer y admin).
- [x] 6. Mano de obra en el costeo (feature 0012).
- [x] 7. Tests (`tests/unit/test_inventory.py`).
- [x] 8. Entrada C-34 en `docs/cambios-api-para-front.md`.

## Frontend
- [x] Admin: Insumos, Movimientos (con ajuste de entrada) y Recetas y costeo con la API.
- [ ] Probar en navegador contra el backend desplegado.

## Datos (después del despliegue)
- [ ] Cargar insumos, stock inicial, recetas reales y el costo del groomer.

## Cierre
- [ ] Spec a `done`, índice actualizado, commit referencia la carpeta.
