---
feature: 0014-dashboard-gerencial
spec: ./spec.md
---

# Plan — Dashboard gerencial v1

## Datos

Sin tablas nuevas ni migración. Se calcula al pedirlo desde `orders`, `order_delay_reports` y
`availability_slots`, más el costeo por orden de `inventory` y las tarifas de `groomer_costs`.

## Código (`app/modules/dashboard/`)

- `domain/dashboard.py`: `METRICS` (clave, etiqueta, unidad, regla), `month_to_date`, `Period`, `ServiceFact`,
  `period_figures` (cifras y calidad `real|estimated|no_data`), `delta`, `outlook` (próximos 7 días).
- `infra/postgres_dashboard_read_repository.py`: canceladas pagadas, servicios solicitados, cupos activos y
  avisos de retraso. Las órdenes terminadas y los cargos extra pagados salen del repositorio de `crm`.
- `app/use_cases.py`: `BuildDashboard` (recibe `cost_of` para poder probarlo sin recetas) y
  `order_cost_estimator(session)`, que usa `GetOrderCost` con las tarifas del día en caché. Si una orden no se
  puede costear, queda sin datos y no tumba el dashboard.
- `api/router.py`: `GET /admin/dashboard?date=YYYY-MM-DD`. Registro en `app/main.py`.

## Admin (`paku-admin`)

- `lib/services/dashboard.ts` con los tipos del endpoint.
- Página `/dashboard/resumen` ("Resumen gerencial", grupo General): tarjetas por cifra con valor, mes anterior,
  diferencia y calidad; tabla de los próximos 7 días; selector del día de corte.

## Riesgos

- Costea cada orden terminada de los dos períodos (varias consultas por orden). Bien con el volumen actual; si
  crece, guardar el costo al terminar la orden o cachear el resultado del día.
- La cancelación usa `updated_at` como fecha: si algo actualiza una orden ya cancelada, se movería de día.
