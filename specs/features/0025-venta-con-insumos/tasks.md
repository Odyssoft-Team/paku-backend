---
feature: 0025-venta-con-insumos
plan: ./plan.md
---

# Tasks — No vender un servicio sin insumos

## Backend
- [x] 1. Disponibilidad de insumos (dominio y caso de uso) y órdenes vendidas pendientes.
- [x] 2. Tienda: `stock_available` y `stock_message` en servicios y adicionales con mascota.
- [x] 3. Pago: 409 `OUT_OF_STOCK` antes de cobrar. C-57.
- [x] 4. Tests (`tests/unit/test_inventory_availability.py`).

## Web
- [x] 5. Elegir servicio y adicionales: «No disponible por ahora»; pago: mensaje de `OUT_OF_STOCK` sin cobro.
