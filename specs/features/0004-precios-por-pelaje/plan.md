---
feature: 0004-precios-por-pelaje
spec: ./spec.md
---

# Plan — Precios por tipo de pelaje

## Enfoque

La categoría de precio vuelve a ser el `coat_type` de la raza del catálogo (`breeds_data`), con
"mestizo" para todo lo demás y como respaldo (comportamiento de respaldo que ya existía en
`price_for`). Se agregan tres endpoints de admin para gestionar la tabla completa y simular, sin tocar
el modelo de datos.

Descartado: mantener official/otros/mestizo (opción B): obligaba a rehacer las tablas cargadas y no
refleja el esfuerzo del servicio.

## Cambios por repo

### paku-backend
- `store/domain/pricing.py` (nuevo): `price_category()`, categorías y etiquetas, tramos sugeridos.
- `store/app/use_cases_impl/quote.py`: `_breed_category` delega en `price_category` (lo usan quote,
  catálogo y `orders/weight_balance`).
- `store/infra/postgres_store_repository.py`: `price_detail_for` (precio + categoría usada) y
  `replace_price_rules` (desactiva + inserta en una transacción).
- `store/app/use_cases_impl/pricing_admin.py` (nuevo): `ReplacePriceMatrix`, `SimulatePrices`,
  `validate_matrix`, `pricing_config`.
- `store/app/use_cases_impl/admin.py`: `CreatePriceRule` valida contra las categorías nuevas.
- `store/api`: esquemas y rutas.

### paku-admin
- Tienda → categoría → precios: tabla por producto/addon, comparación entre productos, alertas
  (celdas vacías, reglas antiguas, precios cruzados), simulador y edición rápida (copiar con %).

## Contrato

- `GET /admin/store/price-config` → `{categories:[{key,label}], fallback_category, weight_tiers:[{weight_min,weight_max}]}`
- `PUT /admin/store/price-matrix/{target_id}` body `{target_type, cells:[{breed_category, weight_min, weight_max, price}], currency}` → `PriceRuleOut[]` (las nuevas activas).
  Errores 422: `PRICE_CATEGORY_INVALID`, `PRICE_INVALID`, `WEIGHT_RANGE_INVALID`, `WEIGHT_RANGE_OVERLAP`, `TARGET_TYPE_INVALID`; 404 si el producto/addon no existe.
- `GET /admin/store/price-simulation?category_id=&weight=&species=dog&breed_id=&breed_name=` →
  `{price_category, price_category_label, products:[{id,name,price,category_used,used_fallback,addons:[…]}]}`

## Migraciones de datos

Ninguna.

## Riesgos

- Mascotas de raza que hoy pagan la fila "mestizo" pasan a pagar la fila de su pelaje: los precios de
  Clásico cambian (ya están cargados por pelaje). Revisar con el negocio antes de desplegar.
- Premium/Express sin filas de pelaje siguen usando su fila "mestizo" hasta que se carguen.
