---
feature: 0011-clientes-crm
spec: ./spec.md
---

# Plan — Clientes (CRM)

## Datos

Sin tablas nuevas. Se calcula al pedirlo desde `orders`, `users`, `user_addresses` y `pets`.

## Código (`app/modules/crm/`)

- `domain/customers.py`: `Visit`, `compute_metrics`, `segment_for` (reglas y umbrales), `visit_from_order`.
- `infra/postgres_customer_read_repository.py`: órdenes terminadas + ajustes pagados (una consulta), usuarios,
  dirección principal y mascotas por lote.
- `app/use_cases.py`: `BuildCustomers`, `ListCustomers` (filtros y orden), `GetCustomerStats`, `GetCustomer`.
- `api/router.py`: `GET /admin/customers`, `/stats`, `/{user_id}`.
- Distrito: nombre desde `geo/infra/districts_data.py`. Tramo de peso de la mascota: `inventory`
  (`weight_code_for`).

## Riesgos

- Se recorren todas las órdenes terminadas en cada pedido: bien con el volumen actual; si crece, cachear o
  guardar un resumen por cliente.
