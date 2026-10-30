---
feature: 0012-costo-groomer
spec: ./spec.md
---

# Plan — Costo del groomer

## Datos (migración `1e2f3a4b5c6d`, no ejecutada)

- `groomer_cost_profiles`: groomer, `effective_from` (único por groomer), sueldo, `items` (JSON
  `{label, kind, value}`), horas al mes, bolsón de manejo y reposo, nota.
- Minutos de groomer: `inventory_recipe_cells.labor_minutes` (migración de 0009).

## Código

- `app/modules/groomer_costs/`: `domain/costs.py` (fórmulas, validación, `profile_on`, `reference_rate`),
  repositorio, `GetLaborRates` / `SaveCostProfile` y `labor_rates(session, day)` para inventario, rutas admin.
- `inventory`: `GetOrderCost` recibe las tarifas del día de la orden; las celdas de receta se costean con la de
  referencia.

## Admin

- `lib/services/groomerCosts.ts`, `components/groomers/GroomerCostSheet.tsx`, columna en Groomers.
