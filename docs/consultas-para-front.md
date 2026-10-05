# Consultas para el front

Preguntas del backend a los equipos de front. Respondidas el 2026-10-05.

| # | Pregunta | Respuesta del front | Acción en backend |
|---|---|---|---|
| 1 | ¿Alguna app usa `PATCH /orders/{id}`? | Ninguna (paku-user, paku-team, paku-web). | **Eliminado** (C-16). |
| 2 | La app de clientes, ¿web o tienda? | Son dos: **paku-user** (móvil, tiendas) y **paku-web** (web). La móvil puede quedar con versiones viejas hasta que actualicen. | Sin cambio en desarrollo. Antes de producción: actualización forzada de paku-user (ver `pendientes.md`). |
| 3 | ¿Qué formato de addons envían al carrito? | Líneas `service_addon` separadas con `meta.base_service_id` (se ignora). El cotizador de paku-web usa `addon_ids` en `POST /store/quote`. | Ya compatible; sin cambio. |
| 4 | ¿Se venden productos físicos (`kind=product`)? | Ninguna app los envía. | Ya se rechazan; sin cambio. |
| 5 | ¿Qué endpoints de carrito usan? | `POST /cart/items`, `PUT /cart/{id}/items`, `DELETE /cart/{id}/items/{item_id}`. No usan `POST /cart/{id}/items`. | Sin cambio. |

## Pedidos del front

| Pedido | Acción |
|---|---|
| Aceptar el aviso de demora también en `created` (las órdenes pasan de `created` a `on_the_way` sin `accepted`; el groomer avisa a la siguiente parada mientras termina la actual). | **Hecho** (C-16). |
