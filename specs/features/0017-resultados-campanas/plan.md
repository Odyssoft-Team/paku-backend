---
feature: 0017-resultados-campanas
spec: ./spec.md
---

# Plan — Resultados de las campañas

- `campaigns/domain/results.py`: `CampaignSale`, `CampaignResult`, `summarize` (puro).
- `PostgresCampaignRepository`: `sold_orders`, `paid_extras`, `done_services`.
- `campaigns/app/use_cases.py`: `BuildCampaignResults(repo, cost_of)`; el costo usa `order_cost_estimator` del
  dashboard.
- `GET /admin/campaigns/results` (antes de `/{campaign_id}`; no choca, esa ruta solo tiene PATCH).
- Admin: `getCampaignResults` y tarjeta en `crm/campanas`; `ventas` lee `campaign_id` de la URL.
- Riesgo: costear cada realizada hace consultas por orden; bien con el volumen actual de campañas.
