---
feature: 0010-parametros-generales
spec: ./spec.md
---

# Plan — Parámetros generales

## Datos (migración `0d1e2f3a4b5c`, no ejecutada)

- `general_settings`: `key` (PK), `value` (JSON), `updated_by`, `updated_at`. Solo los parámetros
  cambiados; los demás usan el valor por defecto del código.

## Código (`app/modules/general_settings/`)

- `domain/settings.py`: lista de parámetros (sección, etiqueta, tipo, valor por defecto, editable, rango),
  `validate_value`, `resolve` y `check_consistency`.
- `infra/`: modelo y repositorio (`get_all`, `get`, `save`, `last_update`).
- `app/use_cases.py`: `GetSettings`, `UpdateSettings` (todo o nada) y `booking_min_days_ahead(session)`.
- `api/router.py`: `GET` y `PATCH /admin/settings`.
- `booking`: `CreateHold.min_days_ahead` y `ListAvailability.execute(min_days_ahead=…)`; las rutas públicas
  leen el parámetro.

## Riesgos

- Una lectura más por cada `GET /availability` y `POST /holds` (una fila por clave primaria).
