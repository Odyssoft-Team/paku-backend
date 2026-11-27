---
feature: 0024-pnl-mensual
spec: ./spec.md
---

# Plan — Cierre mensual / P&L (etapa 1)

## Datos

Sin tablas nuevas ni migración. Lee `orders`, `invoice_documents`, `inventory_movements` y recetas,
`groomer_cost_profiles` y Parámetros generales (dos claves nuevas en `general_settings`, que es clave → valor).

## Código (`app/modules/finance/`)

- `domain/pnl.py`: período del mes (abierto o cerrado), `ServiceFact` (una fila por servicio con venta, insumos,
  minutos y costos), `GroomerMonth`, `build_pnl` (líneas, estados y fuentes), venta sin IGV y receta por fecha.
- `infra/postgres_finance_read_repository.py`: servicios terminados del mes, ajustes, comprobantes vigentes,
  movimientos del mes, canceladas pagadas y groomers.
- `app/use_cases.py`: `BuildMonthlyPnl`; costea cada servicio con la receta vigente a su fecha (reutiliza
  `plan_consumption` de inventario y `GetLaborRates` de groomer_costs).
- `api/router.py`: `GET /admin/finance/pnl?month=YYYY-MM`. Registro en `app/main.py`.
- `inventory`: método nuevo `recipes_for(target_ids)` (todas las versiones). No cambia el costeo existente.
- `general_settings`: sección «Finanzas» con `pos_fee_card_percent` y `pos_fee_yape_percent`.

## Admin (`paku-admin`)

- `lib/services/finance.ts` con los tipos del endpoint.
- `/dashboard/finanzas/cierre`: selector de mes, líneas con estado y detalle (órdenes y movimientos), mano de obra
  real vs receta, por cobrar y pendiente de reembolso. Sale del aviso «Demo» de Finanzas; Pagos y Variable siguen
  como maqueta.

## Riesgos

- Costea cada servicio del mes (varias consultas por orden), como el Dashboard. Bien con el volumen actual.
- El mes no se congela: editar un movimiento o un costo del groomer cambia meses pasados (foto del cierre: etapa 4).
