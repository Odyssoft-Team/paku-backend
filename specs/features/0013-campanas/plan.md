---
feature: 0013-campanas
spec: ./spec.md
---

# Plan — Campañas

## Datos (migración `2f3a4b5c6d7e`, no ejecutada)

- `campaigns` (código único), `campaign_redemptions` (una por orden, `released_at` al cancelar).
- `orders.discount_amount`, `orders.campaign_id`.

## Código (`app/modules/campaigns/`)

- `domain/campaigns.py`: públicos, beneficios, `display_state`, `validate_fields`, `discount_for`,
  `audience_matches`, `best_offer`.
- `infra/`: modelos y repositorio (usos con la regla de pago, resultados, tamaño de públicos).
- `app/use_cases.py`: `SaveCampaign`, `ListCampaigns`, `CampaignEngine.quote`, `campaign_engine(session)`,
  `release_order_campaign`.
- `orders`: `CreateOrderFromCart(campaign_engine=…)` con `campaign_code`; `CancelOrder` libera el uso.

## Apps

- Admin: conectar CRM · Campañas (sigue en maqueta).
- App de clientes: campo de cupón, `POST /campaigns/quote` y `campaign_code` al crear la orden; mostrar
  `discount_amount`.

## Riesgos

- Dos órdenes simultáneas del mismo cliente con un cupón de un uso podrían pasar ambas (sin bloqueo).
- Los fronts que suman los ítems para mostrar el total verán el bruto: deben usar `total_snapshot`.
