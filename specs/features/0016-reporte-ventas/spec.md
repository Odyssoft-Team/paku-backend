---
feature: 0016-reporte-ventas
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin]
creado: 2026-11-01
---

# Reporte de ventas (servicios vendidos)

## Problema

No hay una vista para consultar los servicios vendidos con filtros y exportar. Cierre mensual es una maqueta y
Órdenes es operativa (sin montos agregados ni exportación).

## Objetivo

Una vista con filtros (fechas, estados, medio de pago, servicio, groomer, distrito, campaña, texto), totales,
resúmenes por servicio y por medio de pago, y exportación a CSV.

## Fuera de alcance

- Comprobantes electrónicos, devoluciones y conciliación (no existen todavía).
- Paginación (como el resto del admin).

## Definiciones

- **Venta:** una orden de servicio (sin orden padre). Los cargos extra (órdenes de ajuste) no son filas: se suman a
  su orden, solo si están pagados.
- **Fecha de compra:** cuando se creó la orden (checkout), en hora de Lima. **Fecha del servicio:** cuando terminó;
  si no, la programada; si no, la de la reserva. El filtro de fechas usa una de las dos.
- **Montos:** subtotal = suma de los ítems; descuento = el de la campaña; neto = total de la orden (lo que se
  cobra); cobrado = neto si la orden está pagada + cargos extra pagados. Ticket promedio = cobrado ÷ órdenes pagadas.
- Sin filtro de estado aparecen todas (también las sin pagar y las canceladas); "Pagado" deja las ventas cobradas.
  Una cancelada pagada sigue contando como cobrada (aún no hay devoluciones).

## Criterios de aceptación

- [x] `GET /admin/reports/sales` con filtros, filas, totales, resúmenes y opciones para los filtros.
- [x] Vista "Reporte de ventas" en el menú (Inventario y finanzas) con filtros, exportar y detalle de la orden.
- [x] Sin migración; tests.
