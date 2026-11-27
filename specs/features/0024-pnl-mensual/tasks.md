---
feature: 0024-pnl-mensual
plan: ./plan.md
---

# Tasks — Cierre mensual / P&L (etapa 1)

## Backend
- [x] 1. Parámetros: comisión de tarjeta y de Yape (sección Finanzas).
- [x] 2. Inventario: `recipes_for` (todas las versiones de las recetas) y `OrderConsumption.plan_with`; groomer_costs:
  `rates_from_profiles`. Sin cambio en el costeo existente.
- [x] 3. Módulo `finance`: dominio, lectura, caso de uso y `GET /admin/finance/pnl`. C-56.
- [x] 4. Tests (`tests/unit/test_finance_pnl.py`).

## Admin
- [x] 5. Cierre mensual / P&L conectado a la API, con detalle por línea; quitar «Demo» de esa pantalla.
