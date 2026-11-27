---
feature: 0025-venta-con-insumos
spec: ./spec.md
---

# Plan — No vender un servicio sin insumos

## Backend (sin migración)

- `inventory/domain/availability.py`: `Shortage`, `needs_of`, `merge`, `shortages`, `shortage_message`.
- `inventory/app/availability.py`: `StockAvailability` (disponible = stock − comprometido; `for_pet` para la tienda,
  `order_shortages` para el pago) y `out_of_stock_error`. Reutiliza `OrderConsumption.plan` y `plan_consumption`.
- `inventory` repo: `sold_pending_orders` (pagadas o en verificación, sin realizar ni cancelar).
- `store`: `ListProducts` y `GetProduct` reciben la disponibilidad y marcan `stock_message`; `ProductOut` y `AddonOut`
  con `stock_available` y `stock_message`.
- `orders`: `PayOrder.stock` y `_assert_stock` antes de Culqi.

## Web (paku-web)

- Tipos de servicio y adicional con `stock_available` y `stock_message`.
- Elegir servicio: tarjeta «No disponible por ahora» deshabilitada; adicionales igual.
- Pago: `OUT_OF_STOCK` entre los errores sin cobro, con su mensaje.

## Riesgos

- Planea cada orden vendida pendiente en cada consulta de la tienda (consultas por orden). Bien con el volumen actual;
  si crece, guardar el consumo previsto al pagar.
