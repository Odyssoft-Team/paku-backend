---
feature: 0015-capturas-inventario
plan: ./plan.md
---

# Tasks — Capturas del inventario

## Backend
- [x] 1. Dominio (frecuencias y cortes) y modelos; migración `3a4b5c6d7e8f`.
- [x] 2. Repositorio, casos de uso y tarea programada.
- [x] 3. Rutas `/admin/inventory/snapshots*`; parámetro `inventory_snapshot_frequency` (tipo `choice`).
- [x] 4. Tests (`tests/unit/test_inventory_snapshots.py`).
- [x] 5. Entrada C-40 en `docs/cambios-api-para-front.md`.

## Frontend
- [x] Admin: pestaña Capturas, exportar en Insumos y Movimientos, `choice` en Parámetros.

## Cierre
- [ ] Aplicar la migración en el servidor; spec a `done`.
