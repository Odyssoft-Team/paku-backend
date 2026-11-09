---
feature: 0021-inventario-compras-y-anulacion
spec: ./spec.md
---

# Plan — Ficha del insumo, precio en la compra y anulación

## paku-backend
- Dominio (`inventory/domain/inventory.py`): `CONSUMPTION_UNITS` con `L`; `Supply.brand/description/suppliers`;
  `normalize_suppliers`; `PRICED_MOVEMENT_TYPES`; `weighted_unit_cost`; `Movement.purchase_quantity/purchase_price`,
  `voided_*`, `is_recipe_consumption`, `can_void`.
- Casos de uso: `RegisterMovement` con `purchase_quantity` / `purchase_price` y promedio ponderado en la misma
  transacción; `VoidMovement`; `_supply_fields` valida marca, descripción y proveedores.
- Repositorio: los anulados no cuentan en `stock_by_supply` ni `consumption_totals`; `list_movements(include_voided)`;
  `void_movement` (UPDATE condicionado a `voided_at IS NULL`); nombre de quien anuló.
- API: `POST /admin/inventory/movements/{id}/void`, `include_voided` en el listado, campos nuevos (C-48).
- Migración `7e8f9a0b1c2d` (columnas nuevas, sin backfill).

## paku-admin
- Insumos: marca, descripción y proveedores en el formulario y la ficha; búsqueda y CSV con marca.
- Movimientos: compra en unidades de compra con precio y vista previa del promedio; stock inicial con precio
  opcional; «Anular» con motivo; «Ver anulados»; CSV con precio y anulación.

## Tests
`tests/unit/test_inventory.py`: proveedores y litros, precio y promedio ponderado, reglas del precio, anulación
(stock, errores, consumo por receta no anulable, consumo manual sí) y repositorio real en SQLite.
