---
feature: 0015-capturas-inventario
spec: ./spec.md
---

# Plan — Capturas del inventario

## Datos (migración `3a4b5c6d7e8f`)

- `inventory_snapshots`: corte, tipo (`scheduled|manual`), frecuencia, totales (insumos, valor, bajo mínimo,
  agotados), quién y cuándo. `schedule_key` único (= corte en ISO, solo automáticas) evita duplicados aunque
  corran varias instancias.
- `inventory_snapshot_lines`: una fila por insumo con copia de sus datos, stock, mínimo, costo, valor y estado.

## Código

- `inventory/domain/snapshots.py`: frecuencias, `is_cut_day`, `due_cut` (recupera hasta 3 días), `next_cut`.
- `inventory/infra/postgres_snapshot_repository.py`: crear (con la clave única), listar y leer.
- `inventory/infra/postgres_inventory_repository.py`: `stock_by_supply(until=)` filtra por fecha del movimiento.
- `inventory/app/snapshots.py`: `TakeSnapshot` (reglas de Insumos: `supply_row`), `RunScheduledSnapshot`,
  `GetSnapshot` y la tarea `run_scheduled_snapshot_job`, registrada en `app/core/scheduler.py` cada 30 min.
- `inventory/api/router.py`: `GET /admin/inventory/snapshots`, `GET …/{id}`, `POST …` (manual).
- `general_settings`: tipo `choice` con `options` y el parámetro `inventory_snapshot_frequency` (sección Inventario).

## Admin

- Pestaña Inventario · Capturas: lista por rango de corte, detalle con filtros, exportar y "Tomar captura ahora".
- Exportar CSV en Insumos y Movimientos. Parámetros: el tipo `choice` se muestra como lista.

## Riesgos

- La captura automática necesita que el servidor esté encendido dentro de los 3 días siguientes al corte.
- Si hay varias instancias, todas corren la tarea; la clave única deja una sola captura por corte.
