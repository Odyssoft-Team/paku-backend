---
feature: 0005-requisitos-servicio
spec: ./spec.md
---

# Plan — Requisitos del servicio

## Datos

- `store_products.max_weight_kg` (float, null) y `max_age_months` (int, null). Migración
  `6f7a8b9c0d1e`, que además actualiza `breeds` (la tabla solo se siembra si está vacía).
- Edad = meses cumplidos desde `pets.birth_date`.

## Cambios

- `store/domain/eligibility.py`: `age_in_months`, `ineligibility(product, weight, birth_date)` →
  `(código, mensaje)` o None.
- `price_service(..., check_requirements=False)`: `Quote` y `CartPricing` pasan True; el saldo por peso no.
- `ListProducts` / `GetProduct` con `pet_id`: filtran no elegibles y sin precio.
- `SimulatePrices`: omite productos sobre el peso máximo.
- Admin: `POST/PATCH /admin/store/products` aceptan los dos campos (PATCH: null quita el límite,
  omitir lo deja igual); `ProductOut` los devuelve.
- `catalog/domain/breeds_data.py`: Pug → `double_short`, Pekinés → `double_long`, + 3 razas.

## Riesgos

- Mascotas Pug/Pekinés existentes cambian de precio (sube): esperado según el documento.
- Un cachorro sin fecha de nacimiento no verá Express sin agua: el mensaje de la cotización lo explica.
