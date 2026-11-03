---
feature: 0019-simulador-servicio
spec: ./spec.md
---

# Plan — Simulador de un servicio

## Enfoque

`SimulateService` (`app/modules/inventory/app/simulation.py`) arma los `ConsumptionTarget` del servicio y sus
adicionales y reutiliza `plan_consumption` (misma celda que una orden), `price_for` de la tabla de precios y
`LaborRates.rate_for(groomer_id)`. Agrega el consumo por insumo y lo compara con `stock_by_supply()`. Sin migración.

## Cambios por repo

### paku-backend
- `POST /admin/inventory/simulate` (router de inventario), esquemas `Simulation*`.

### paku-admin
- Pestaña «Simulador de servicio» en Inventario → Recetas y costeo (`components/inventory/ServiceSimulator.tsx`).

## Contrato

`POST /admin/inventory/simulate` `{product_id, addon_ids, breed_id?, weight_kg, groomer_id?}` → C-46.

## Tests

`tests/unit/test_inventory_simulation.py`: costos y margen, respaldo mestizo, consumo frente al stock, avisos por
falta de receta, precio o tarifa, peso fuera del límite del servicio, errores y la respuesta de la API.
