---
feature: 0004-precios-por-pelaje
plan: ./plan.md
---

# Tasks — Precios por tipo de pelaje

## Backend
- [x] `price_category()` por pelaje del catálogo, respaldo "mestizo"
- [x] Cotización, catálogo y saldo por peso usan la nueva categoría
- [x] `price_detail_for` y `replace_price_rules` en el repositorio
- [x] `GET /admin/store/price-config`, `PUT /admin/store/price-matrix/{id}`, `GET /admin/store/price-simulation`
- [x] `CreatePriceRule` acepta pelajes + "mestizo"
- [x] Tests (`tests/unit/test_store_pricing_by_coat.py`)
- [x] Entrada C-25 en `docs/cambios-api-para-front.md`

## paku-admin
- [ ] Tabla pelaje × peso por producto y addon, con guardado completo
- [ ] Comparar productos y alerta de precios cruzados
- [ ] Alertas: celdas vacías, reglas antiguas, productos sin precio
- [ ] Simulador raza + peso
- [ ] Copiar tabla con % y ajuste por fila

## Cierre
- [ ] Negocio carga Premium, Express y addons
- [ ] Desactivar reglas "official"/"otros"
- [ ] Spec a estado `done`
