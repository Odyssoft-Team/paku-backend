---
feature: 0017-resultados-campanas
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin]
creado: 2026-11-01
---

# Resultados de las campañas

## Problema

La lista de campañas solo muestra usos pagados, descuento y ventas netas. No dice si la campaña trajo clientes
nuevos, cuánto se cobró en total ni si dejó margen.

## Objetivo

Por campaña (y el total de todas): vendidas y realizadas, clientes y nuevos, descuento, cobrado, costo estimado y
margen. Se ve en CRM · Campañas, con exportar CSV y enlace al reporte de ventas filtrado por la campaña.

## Fuera de alcance

- Filtrar por fechas dentro de la campaña (se mide desde su inicio; el detalle por fecha está en Reporte de ventas).
- Atribución de clientes que compraron sin la campaña después de recibir un aviso (aún no se envían avisos).

## Definiciones

- **Vendidas:** órdenes de servicio con la campaña, pagadas y no canceladas (igual que «usos en órdenes pagadas» de
  la lista). **Realizadas:** de ellas, las terminadas.
- **Cliente nuevo:** antes de su primera compra con la campaña no tenía ningún servicio terminado fuera de esa
  campaña. En el total, fuera de cualquier campaña. Momento del servicio: terminó; si no, programada; si no, creación.
- **Montos:** subtotal = suma de los ítems; descuento = el de la campaña; neto = total de la orden; cobrado = neto +
  cargos extra pagados.
- **Costo estimado:** el del dashboard (insumos registrados o de la receta + minutos de receta × costo por hora),
  solo de las realizadas. Las que no se pueden costear (sin receta o sin tarifa) quedan fuera; se informa cuántas
  tienen costo. **Margen** = cobrado de las costeadas − su costo; % sobre ese cobrado. Sin ninguna costeada: null.

## Criterios de aceptación

- [x] `GET /admin/campaigns/results` con resultados por campaña (las sin ventas en cero) y el total.
- [x] Tarjeta «Resultados» en CRM · Campañas (respeta el filtro de período), exportar CSV y «Ver ventas».
- [x] Reporte de ventas acepta `?campaign_id=`.
- [x] Sin migración; tests.
