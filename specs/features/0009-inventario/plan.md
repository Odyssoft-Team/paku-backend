---
feature: 0009-inventario
spec: ./spec.md
---

# Plan — Inventario

## Datos (migración `9c0d1e2f3a4b`, no ejecutada)

- `inventory_supplies`: `sku` único (`INS-001`), nombre, categoría, unidad y contenido de compra, unidad de
  consumo, costo de compra, stock mínimo, control de lote / vencimiento, `is_active`.
- `inventory_movements`: `seq` (identity, `MOV-0001`), fecha, tipo, insumo, cantidad con signo, `unit_cost`,
  ubicación, centro de costo, `order_id`, `recipe_id`, `recipe_cell_id`, motivo, lote, vencimiento,
  `created_by` (null = sistema).
- `inventory_recipes` (una fila por versión: `target_type`, `target_id`, `version`, `is_current`),
  `inventory_recipe_cells` (`breed_category`, `weight_min`, `weight_max`, `labor_minutes`) e
  `inventory_recipe_lines` (celda, insumo, cantidad).

## Código (`app/modules/inventory/`)

- `domain/inventory.py`: entidades, listas fijas, `find_cell` (misma regla que `price_detail_for`: pelaje o
  "mestizo", tramo con el peso redondeado al centésimo), `plan_consumption`.
- `infra/`: modelos y repositorio (stock por `SUM`, recetas con celdas y líneas).
- `app/use_cases.py`: insumos, movimientos, `SaveRecipe` (valida con `validate_matrix` de precios),
  `OrderConsumption`, `GetOrderCost` (insumos + mano de obra con `groomer_costs.LaborRates`), resumen.
- `app/order_hook.py`: consumo best effort al pasar a `done` (`CompleteOrder` y `_change_status_as_staff`).

## API (admin)

| Método | Ruta | Uso |
|---|---|---|
| GET | `/admin/inventory/config` | listas fijas (filas y tramos: `/admin/store/price-config`) |
| GET / POST · PATCH | `/admin/inventory/supplies` · `/{id}` | insumos |
| GET / POST | `/admin/inventory/movements` | movimientos |
| GET | `/admin/inventory/summary` | tarjetas de Insumos |
| GET | `/admin/inventory/recipes` | servicios y adicionales con receta |
| GET / PUT | `/admin/inventory/recipes/{target_id}` | tabla vigente (con costo, precio y margen por celda) / nueva versión |
| GET | `/admin/inventory/recipes/{target_id}/versions` | historial |
| GET | `/admin/inventory/orders/{order_id}/cost` | costeo de la orden |
| POST | `/admin/inventory/orders/{order_id}/consume` | registrar el consumo de una orden terminada |

## Admin (`paku-admin`)

- `lib/services/inventory.ts`; páginas `inventario/*` sin la maqueta; `components/inventory/RecipeMatrixEditor.tsx`
  (capas: costo y margen, minutos, un insumo por capa; copiar de otro servicio; "→ fila").

## Riesgos

- El hook comparte la sesión de la orden: si falla, rollback del consumo (se reintenta con `/consume`).
- Listados sin paginar (como el resto del admin); movimientos con `limit`.
