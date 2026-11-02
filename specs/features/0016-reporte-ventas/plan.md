---
feature: 0016-reporte-ventas
spec: ./spec.md
---

# Plan — Reporte de ventas

- Módulo nuevo `app/modules/reports/` (solo lectura, sin migración):
  - `domain/sales.py`: `SaleRow`, `SalesFilters`, filtros (`in_range`, `matches`), `totals` y `group`.
  - `infra/postgres_sales_read_repository.py`: órdenes de servicio (acotadas por creación si el filtro es por
    compra), cargos extra pagados, usuarios, mascotas y campañas por lote.
  - `app/use_cases.py`: `BuildSalesReport`; las opciones de los filtros salen de las filas del rango de fechas.
  - `api/router.py`: `GET /admin/reports/sales`. Registro en `app/main.py`.
- Admin: `lib/services/sales.ts` y página `/dashboard/ventas`.
- Riesgo: con filtro por fecha del servicio se leen todas las órdenes de servicio; bien con el volumen actual.
